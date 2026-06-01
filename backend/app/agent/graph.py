"""LangGraph ReAct agent for complex / multi-step queries.

Only invoked when the router returns Intent.GENERAL.
"""
from __future__ import annotations
from typing import Annotated, AsyncIterator, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.llm_provider import get_llm
from app.agent.tools.search_parts import search_parts
from app.agent.tools.check_compatibility import check_compatibility
from app.agent.tools.list_compatible_parts import list_compatible_parts
from app.agent.tools.get_installation import get_installation_guide
from app.agent.tools.add_to_cart import add_to_cart as _add_to_cart
from app.agent.tools.remove_from_cart import remove_from_cart as _remove_from_cart
from app.config import load_settings
from app.observability import get_logger, log_event, safe_preview

log = get_logger("agent.graph")

SYSTEM_PROMPT = """You are a specialized AI assistant for PartSelect, an appliance parts e-commerce platform.

Your PRIMARY function is product information and customer transactions for Refrigerator and Dishwasher parts. You help customers:
- Find parts by part number, symptom, or description
- Check part compatibility with specific appliance models (use check_compatibility_tool)
- List parts verified compatible with a model (use list_compatible_parts_tool)
- Get installation instructions for parts
- Add or remove parts from their cart (handled by the app router — do not use cart tools here)

For troubleshooting or repair questions, do NOT attempt a diagnosis. Respond with exactly:
"PartSelect has many resources to help you with troubleshooting and repairing your products. For helpful articles and how-to videos you can visit https://www.partselect.com/Repair/. To get help finding parts that may fix the issue you are facing you can also try our Instant Repairman feature at https://www.partselect.com/Instant-Repairman/."

If a user asks about anything outside Refrigerator and Dishwasher parts, politely decline.

IMPORTANT:
- Respond to the user's LATEST message only. Prior messages are background context.
- Do NOT assume or invent an appliance model. Only use a model number the user provided this turn or in an explicit [My appliance model: ...] prefix.
- Never claim compatibility unless check_compatibility_tool or list_compatible_parts_tool confirms it.
- When a tool result has source: "live", tell the user the data was fetched live from PartSelect. If complete is false or missing_fields is set, say which details are unavailable — do not guess.

Be specific: include part numbers, prices, and links when recommending parts."""


def _make_tools(session_id: str, *, include_cart: bool = False):
    from langchain_core.tools import tool

    @tool
    def search_parts_tool(query: str, category: str | None = None) -> list[dict]:
        """Search parts by keyword or PS number. Does NOT verify model compatibility."""
        return search_parts(query, category)

    @tool
    def list_compatible_parts_tool(
        model_number: str, part_query: str | None = None
    ) -> dict:
        """List parts verified compatible with an appliance model (from compatibility database)."""
        return list_compatible_parts(model_number, part_query)

    @tool
    def check_compatibility_tool(model_number: str, part_number_or_query: str) -> dict:
        """Check if a specific part is compatible with a model number."""
        return check_compatibility(model_number, part_number_or_query)

    @tool
    def get_installation_guide_tool(part_number: str) -> dict:
        """Get step-by-step installation instructions for a part number."""
        return get_installation_guide(part_number)

    tools = [
        search_parts_tool,
        list_compatible_parts_tool,
        check_compatibility_tool,
        get_installation_guide_tool,
    ]

    if include_cart:
        @tool
        def add_to_cart_tool(ps_number: str, quantity: int = 1) -> dict:
            """Add a part to the user's cart by PS number."""
            return _add_to_cart(session_id, ps_number, quantity)

        @tool
        def remove_from_cart_tool(ps_number: str) -> dict:
            """Remove a part from the user's cart by PS number."""
            return _remove_from_cart(session_id, ps_number)

        tools.extend([add_to_cart_tool, remove_from_cart_tool])

    return tools


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def build_graph(session_id: str):
    tools = _make_tools(session_id)
    llm = get_llm("synthesis").bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = llm.invoke(messages)
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()


async def run_agent_streaming(
    session_id: str,
    message: str,
    appliance_model: str | None,
    history: list,
) -> AsyncIterator[str]:
    """Yield LLM text tokens from the LangGraph agent."""
    settings = load_settings()
    log_event(
        log,
        "agent.invoke.start",
        session_id=session_id,
        model=settings.llm.synthesis_model,
        has_appliance_model=bool(appliance_model),
        message=safe_preview(message),
        history_count=len(history),
    )
    graph = build_graph(session_id)
    content = message
    if appliance_model and appliance_model.strip():
        content = f"[My appliance model: {appliance_model.strip()}]\n{message}"
    user_msg = HumanMessage(content=content)
    input_messages = history + [user_msg]

    def _content_from_chunk(raw: object) -> str:
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw
        if isinstance(raw, list):
            return "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in raw
            )
        return str(raw)

    emitted = False
    token_count = 0
    char_count = 0
    logged_tools: set[tuple[str, str]] = set()
    try:
        async for event in graph.astream_events(
            {"messages": input_messages},
            version="v2",
        ):
            event_name = event.get("event") or ""
            if "tool" in event_name:
                tool_name = event.get("name") or event.get("metadata", {}).get("langgraph_node") or ""
                marker = (event_name, str(tool_name))
                if marker not in logged_tools:
                    logged_tools.add(marker)
                    log_event(log, "agent.tool.transition", session_id=session_id, event=event_name, tool=tool_name)
            if event.get("event") != "on_chat_model_stream":
                continue
            chunk = event.get("data", {}).get("chunk")
            if chunk is None:
                continue
            token = _content_from_chunk(getattr(chunk, "content", None))
            if token:
                emitted = True
                token_count += 1
                char_count += len(token)
                yield token
    except Exception:
        log.exception("agent.astream_events failed session=%s", session_id)
        log_event(log, "agent.stream.error", session_id=session_id, path="astream_events")
        yield "Sorry, something went wrong while processing that. Please try rephrasing your question."
        return

    if emitted:
        log_event(log, "agent.stream.done", session_id=session_id, token_count=token_count, char_count=char_count)
        return

    try:
        result = await graph.ainvoke({"messages": input_messages})
    except Exception:
        log.exception("agent.invoke failed session=%s", session_id)
        log_event(log, "agent.invoke.error", session_id=session_id, path="ainvoke")
        yield "Sorry, something went wrong while processing that. Please try rephrasing your question."
        return

    final_msg = result["messages"][-1]
    text = _content_from_chunk(getattr(final_msg, "content", str(final_msg)))
    if not text.strip():
        log.warning("agent returned empty text session=%s", session_id)
        text = "I couldn't complete that request. Please try again or rephrase your question."
    log_event(log, "agent.stream.done", session_id=session_id, token_count=1, char_count=len(text))
    yield text

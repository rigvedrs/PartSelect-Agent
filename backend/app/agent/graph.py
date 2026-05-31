"""LangGraph ReAct agent for complex / multi-step queries.

Only invoked when the deterministic router returns Intent.COMPLEX or TROUBLESHOOT.
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
from app.agent.tools.troubleshoot import troubleshoot_symptom
from app.agent.tools.add_to_cart import add_to_cart as _add_to_cart
from app.agent.tools.remove_from_cart import remove_from_cart as _remove_from_cart
from app.observability import get_logger

log = get_logger("agent.graph")

SYSTEM_PROMPT = """You are a specialized AI assistant for PartSelect, an appliance parts e-commerce platform.

Your ONLY area of expertise is Refrigerator and Dishwasher parts. You help customers:
- Find parts by part number, symptom, or description
- Check part compatibility with specific appliance models (use check_compatibility_tool)
- List parts verified compatible with a model (use list_compatible_parts_tool — SQL-backed, only returns real compat rows)
- Get installation instructions for parts
- Troubleshoot appliance issues and identify which parts to replace
- Add or remove parts from their cart

If a user asks about anything outside Refrigerator and Dishwasher parts, politely decline.

IMPORTANT:
- Respond to the user's LATEST message only. Prior messages are background context.
- Do NOT assume or invent an appliance model. Only use a model number if the user provided one in the latest message or in an explicit [My appliance model: ...] prefix on this turn.
- Never claim compatibility unless check_compatibility_tool or list_compatible_parts_tool confirms it.
- When listing parts for a model, use list_compatible_parts_tool — do not guess from general search.

Be specific: include part numbers, prices, and links when recommending parts."""


def _make_tools(session_id: str):
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

    @tool
    def troubleshoot_symptom_tool(symptom: str, appliance_type: str, brand: str | None = None) -> dict:
        """Troubleshoot a symptom and get repair-guide matches."""
        return troubleshoot_symptom(symptom, appliance_type, brand)

    @tool
    def add_to_cart_tool(ps_number: str, quantity: int = 1) -> dict:
        """Add a part to the user's cart by PS number."""
        return _add_to_cart(session_id, ps_number, quantity)

    @tool
    def remove_from_cart_tool(ps_number: str) -> dict:
        """Remove a part from the user's cart by PS number."""
        return _remove_from_cart(session_id, ps_number)

    return [
        search_parts_tool,
        list_compatible_parts_tool,
        check_compatibility_tool,
        get_installation_guide_tool,
        troubleshoot_symptom_tool,
        add_to_cart_tool,
        remove_from_cart_tool,
    ]


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def build_graph(session_id: str):
    tools = _make_tools(session_id)
    llm = get_llm("tool").bind_tools(tools)

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
    """Yield text tokens. `history` is prior user/assistant LangChain messages for this session."""
    graph = build_graph(session_id)
    content = message
    if appliance_model and appliance_model.strip():
        content = f"[My appliance model: {appliance_model.strip()}]\n{message}"
    user_msg = HumanMessage(content=content)
    try:
        result = await graph.ainvoke({"messages": history + [user_msg]})
    except Exception:
        log.exception("agent.invoke failed session=%s", session_id)
        yield "Sorry, something went wrong while processing that. Please try rephrasing your question."
        return
    final_msg = result["messages"][-1]
    text = getattr(final_msg, "content", str(final_msg))
    if isinstance(text, list):
        text = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in text
        )
    if not text.strip():
        log.warning("agent returned empty text session=%s", session_id)
    chunk_size = 20
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]

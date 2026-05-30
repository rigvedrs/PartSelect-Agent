"""LangGraph ReAct agent for complex / multi-step queries.

Only invoked when the deterministic router returns Intent.COMPLEX or TROUBLESHOOT.
"""
from __future__ import annotations
from typing import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.llm_provider import get_llm
from app.agent.tools.search_parts import search_parts
from app.agent.tools.check_compatibility import check_compatibility
from app.agent.tools.get_installation import get_installation_guide
from app.agent.tools.troubleshoot import troubleshoot_symptom
from app.agent.tools.add_to_cart import add_to_cart as _add_to_cart

SYSTEM_PROMPT = """You are a specialized AI assistant for PartSelect, an appliance parts e-commerce platform.

Your ONLY area of expertise is Refrigerator and Dishwasher parts. You help customers:
- Find parts by part number, symptom, or description
- Check part compatibility with specific appliance models
- Get installation instructions for parts
- Troubleshoot appliance issues and identify which parts to replace
- Add parts to their cart

If a user asks about anything outside Refrigerator and Dishwasher parts, politely decline and explain you can only assist with refrigerator and dishwasher parts.

Always be specific. When recommending a part, include the part number, price, and a direct link. When giving installation steps, be step-by-step and clear. When checking compatibility, be definitive — say "yes, compatible" or "not compatible" with a reason.

The user may have already set their appliance model number. If they have, use it automatically."""


def _make_tools(session_id: str):
    """Bind session_id into add_to_cart so the LLM only needs to pass ps_number."""
    from langchain_core.tools import tool

    @tool
    def search_parts_tool(query: str, category: str | None = None) -> list[dict]:
        """Search for refrigerator or dishwasher parts by part number, name, or description."""
        return search_parts(query, category)

    @tool
    def check_compatibility_tool(model_number: str, part_number_or_query: str) -> dict:
        """Check if a part is compatible with a specific appliance model number."""
        return check_compatibility(model_number, part_number_or_query)

    @tool
    def get_installation_guide_tool(part_number: str) -> dict:
        """Get step-by-step installation instructions for a part number."""
        return get_installation_guide(part_number)

    @tool
    def troubleshoot_symptom_tool(symptom: str, appliance_type: str, brand: str | None = None) -> dict:
        """Troubleshoot an appliance symptom and get recommended parts to fix it."""
        return troubleshoot_symptom(symptom, appliance_type, brand)

    @tool
    def add_to_cart_tool(ps_number: str, quantity: int = 1) -> dict:
        """Add a part to the user's cart by PS number."""
        return _add_to_cart(session_id, ps_number, quantity)

    return [search_parts_tool, check_compatibility_tool, get_installation_guide_tool,
            troubleshoot_symptom_tool, add_to_cart_tool]


def build_graph(session_id: str):
    tools = _make_tools(session_id)
    llm = get_llm("tool").bind_tools(tools)

    def agent_node(state: dict) -> dict:
        messages = state.get("messages", [])
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = llm.invoke(messages)
        return {"messages": messages + [response]}

    graph = StateGraph(dict)
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
    if appliance_model:
        content = f"[My appliance model: {appliance_model}]\n{message}"
    user_msg = HumanMessage(content=content)
    result = await graph.ainvoke({"messages": history + [user_msg]})
    final_msg = result["messages"][-1]
    text = getattr(final_msg, "content", str(final_msg))
    chunk_size = 20
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]

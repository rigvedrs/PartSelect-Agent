from functools import lru_cache
from langchain_openai import ChatOpenAI
from app.config import load_settings


@lru_cache(maxsize=2)
def get_llm(role: str = "tool") -> ChatOpenAI:
    """Return a ChatOpenAI instance for the given role.

    role='tool'      → fast model, temperature=0 (tool-calling decisions)
    role='synthesis' → stronger model, higher temp (natural language responses)

    All model slugs and temperatures come from config.toml — no hardcoding.
    """
    s = load_settings()
    model = s.llm.tool_model if role == "tool" else s.llm.synthesis_model
    temp = s.llm.tool_temperature if role == "tool" else s.llm.synthesis_temperature
    return ChatOpenAI(
        model=model,
        openai_api_key=s.llm.api_key or "placeholder",
        openai_api_base=s.llm.base_url,
        streaming=True,
        temperature=temp,
    )

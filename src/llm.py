"""Lazy LLM construction so health checks and database tests do not require an LLM key."""
from functools import lru_cache

from langchain_groq import ChatGroq

from .config import settings


@lru_cache
def get_llm() -> ChatGroq:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    return ChatGroq(
        model=settings.model_name,
        temperature=0,
        api_key=settings.groq_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


# Kept for compatibility with code that imports `llm`.
class _LazyLLM:
    def __getattr__(self, name):
        return getattr(get_llm(), name)


llm = _LazyLLM()

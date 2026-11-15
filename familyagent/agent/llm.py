"""Chat model factory. The client is created on first use, not at import time."""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from familyagent.config import config


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.DASHSCOPE_API_KEY,
        base_url=config.DASHSCOPE_BASE_URL,
        timeout=config.LLM_TIMEOUT_SECONDS,
    )

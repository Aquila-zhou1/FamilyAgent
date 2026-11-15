"""Chess assistant.

Iteration 0: plain LLM chat with a chess system prompt, no tools.
Iteration 3 replaces this with an agent that calls MCP tools.
"""

import logging
from collections.abc import Iterator

from langchain_core.messages import HumanMessage, SystemMessage

from familyagent.agent.llm import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a chess assistant. You help with chess openings and Lichess puzzles. "
    "Be concise. If you are not sure about a move or an opening name, say so "
    "instead of guessing."
)

LANGUAGE_INSTRUCTION = {
    "en": "Answer in English.",
    "zh": "请用简体中文回答。",
}

ERROR_MESSAGE = {
    "en": "Sorry, the assistant is unavailable right now. Please try again later.",
    "zh": "抱歉，助手暂时不可用，请稍后再试。",
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in LANGUAGE_INSTRUCTION else "en"


def stream_answer(question: str, lang: str = "en") -> Iterator[str]:
    """Yield the answer as text chunks. Errors become one readable message."""
    lang = normalize_lang(lang)
    messages = [
        SystemMessage(content=f"{SYSTEM_PROMPT} {LANGUAGE_INSTRUCTION[lang]}"),
        HumanMessage(content=question),
    ]
    try:
        for chunk in get_llm().stream(messages):
            if chunk.content:
                yield chunk.content
    except Exception:
        logger.exception("LLM call failed")
        yield ERROR_MESSAGE[lang]

"""Chess assistant: a tool-calling agent over the two MCP servers."""

import logging
import time
from collections.abc import AsyncIterator

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from familyagent.agent.llm import get_llm
from familyagent.agent.tools import TOOL_ERROR_PREFIX, describe_error, load_tools, to_text
from familyagent.config import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a chess assistant for chess openings and Lichess puzzles.

Tools:
- search_openings(query): look up an opening by NAME.
- find_opening_by_moves(moves): identify the opening reached by a sequence of MOVES.
- get_daily_puzzle(): today's Lichess puzzle.
- get_puzzle(puzzle_id): a Lichess puzzle by ID.

Rules:
1. Opening names, opening moves, ECO codes, puzzle solutions and puzzle details must come
   from a tool result in this conversation. Never state them from memory.
2. General chess knowledge (rules, how pieces move, basic principles) needs no tool.
3. If the user's request is missing something a tool needs (for example a puzzle ID),
   ask for it instead of guessing.
4. If a tool result starts with "TOOL_ERROR:", or a needed tool is unavailable, tell the
   user plainly that the lookup failed and why. Do not give any opening name, move or
   solution in its place.
5. If a search returns no match, or only results whose names do not match what was asked,
   say that the opening was not found. Do not present a different opening as the answer.
6. When you report a puzzle solution, copy the moves from the tool result in order:
   the solution_san moves (if present) and the solution_uci moves, for example
   "Qxh6+ Rh7 Qxf8# (UCI: g6h6 f7h7 h6f8)". Do not convert notation yourself, do not
   rename or reorder moves, and do not describe pieces, captures or squares that the
   tool result does not state.
7. To find the opening of a puzzle's game, pass that game's moves (game_moves_san) to
   find_opening_by_moves. Never name the opening of a game from the moves yourself.
8. Be concise."""

LANGUAGE_INSTRUCTION = {
    "en": "Answer in English.",
    "zh": "请用简体中文回答（开局名称和着法保持原文）。",
}

ERROR_MESSAGE = {
    "en": "Sorry, the assistant is unavailable right now. Please try again later.",
    "zh": "抱歉，助手暂时不可用，请稍后再试。",
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in LANGUAGE_INSTRUCTION else "en"


def build_system_prompt(lang: str, unavailable: list[str]) -> str:
    parts = [SYSTEM_PROMPT, LANGUAGE_INSTRUCTION[lang]]
    if unavailable:
        parts.append(
            "Currently unavailable tool servers: "
            + ", ".join(unavailable)
            + ". Their tools cannot be called. If the question needs them, apply rule 4."
        )
    return "\n\n".join(parts)


def extract_tool_calls(messages: list) -> list[dict]:
    """The tool calls that were actually executed, in order, with their outcome."""
    calls: dict[str, dict] = {}
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                calls[call["id"]] = {
                    "name": call["name"],
                    "args": call["args"],
                    "ok": None,  # stays None if the tool never ran
                    "result": None,
                }
        elif isinstance(message, ToolMessage):
            record = calls.get(message.tool_call_id)
            if record is None:
                continue
            text = to_text(message.content)
            failed = text.startswith(TOOL_ERROR_PREFIX) or message.status == "error"
            record["ok"] = not failed
            record["result"] = text[:1000]
    return list(calls.values())


async def _prepare(question: str, lang: str):
    tools, unavailable = await load_tools()
    agent = create_agent(
        model=get_llm(),
        tools=tools,
        system_prompt=build_system_prompt(lang, unavailable),
    )
    payload = {"messages": [HumanMessage(content=question)]}
    run_config = {"recursion_limit": config.AGENT_MAX_STEPS}
    return agent, payload, run_config, unavailable


async def ask(question: str, lang: str = "en") -> dict:
    """Answer one question. Never raises: failures are reported in the result."""
    lang = normalize_lang(lang)
    started = time.perf_counter()
    result = {
        "answer": ERROR_MESSAGE[lang],
        "tool_calls": [],
        "unavailable_servers": [],
        "error": None,
    }
    try:
        agent, payload, run_config, unavailable = await _prepare(question, lang)
        result["unavailable_servers"] = unavailable
        state = await agent.ainvoke(payload, config=run_config)
        messages = state["messages"]
        result["tool_calls"] = extract_tool_calls(messages)
        answer = to_text(messages[-1].content).strip()
        if answer:
            result["answer"] = answer
        else:
            result["error"] = "empty_answer"
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent run failed: %s", describe_error(exc))
        logger.debug("agent run traceback", exc_info=True)
        result["error"] = describe_error(exc)
    result["latency_ms"] = round((time.perf_counter() - started) * 1000)
    return result


async def stream_answer(question: str, lang: str = "en") -> AsyncIterator[str]:
    """Yield the answer text as it is generated (tool activity is not shown)."""
    lang = normalize_lang(lang)
    produced = False
    try:
        agent, payload, run_config, _ = await _prepare(question, lang)
        async for chunk, _metadata in agent.astream(
            payload, config=run_config, stream_mode="messages"
        ):
            if isinstance(chunk, AIMessageChunk):
                text = to_text(chunk.content)
                if text:
                    produced = True
                    yield text
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent stream failed: %s", describe_error(exc))
        logger.debug("agent stream traceback", exc_info=True)
        if produced:
            yield "\n\n"
        yield ERROR_MESSAGE[lang]
        return
    if not produced:
        yield ERROR_MESSAGE[lang]

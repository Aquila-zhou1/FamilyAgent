# Chess Agent

[中文说明](README_CN.md)

A FastAPI + LangChain chess assistant. The goal is an agent that answers questions about chess openings and Lichess puzzles through MCP tools, runs on a local Kubernetes cluster, and is measured on 100 evaluation cases.

**Status: iteration 0 of 7.** The app starts and chats through the model. Tools, MCP, Kubernetes and the evaluation are not built yet. The step-by-step plan is in `plan/CHESS_ITERATIONS.md` (kept locally, not committed).

## Setup (Windows, PowerShell)

```powershell
uv sync
.venv\Scripts\activate
copy .env.example .env   # then fill in the key and base URL
```

## Run

```powershell
python -m familyagent
```

| URL | Purpose |
| --- | --- |
| `http://127.0.0.1:8000/agent/chess` | Chat page (English by default, one-click switch to Chinese) |
| `http://127.0.0.1:8000/docs` | API documentation |
| `http://127.0.0.1:8000/healthz` | Liveness check, does not call the model |

`POST /agent/chess/stream` takes JSON `{"question": "...", "lang": "en"}` and streams plain text.

## Checks

```powershell
pytest                        # no network, no real key needed
python scripts/check_llm.py   # one real model call; prints no secrets
```

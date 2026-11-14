# FamilyAgent

[中文说明](README_CN.md)

A Python 3.11 / FastAPI prototype for family health knowledge retrieval and weather-aware travel planning. It uses LangChain, Alibaba Cloud DashScope's OpenAI-compatible API, DashVector, and Jinja2 pages with Vue 3 loaded from a CDN.

## What exists

| Component | Current implementation |
| --- | --- |
| Medical RAG | CSV ingestion, recursive text splitting, remote embeddings, DashVector search, and LLM answers grounded in retrieved content. Health queries request the top 3 results. |
| Knowledge data | Four Chinese records covering children, older adults, and infants in `familyagent/data/health_knowledge.csv`. These are demo records; source authority is not established. |
| Tools | `health_knowledge_search` and `get_weather`, registered when LangChain agents are constructed. Weather uses hardcoded examples and a default forecast, not a live API. |
| Actual request path | Health streams explicitly retrieve then call the LLM; travel streams call the LLM directly. Neither stream executes the constructed agent's tool loop. Health also retrieves twice per streamed request. |
| Routing | LLM intent classification dispatches health, travel/weather, or general chat requests. |
| UI | Three Chinese chat pages with streamed responses; no separate frontend build is needed. |
| Tests | Provider/debug scripts, not a reproducible evaluation suite. Some scripts make network calls; `test_config.py` prints an API key. |

MCP, containers, Kubernetes manifests, a 100-case evaluation, and measured Recall@3/tool accuracy/p95 results are **not implemented or demonstrated**.

## Startup with uv

The commands below describe the recovery procedure; they were **not executed as an application startup** during this documentation-only review. Existing code may need compatibility fixes first.

Run PowerShell from the repository root. Recreate an environment locally rather than copying another machine's `.venv`. At review time, uv was installed, this project had no `.venv`, and bare `python` resolved to another project's environment.

```powershell
uv --version
uv python install 3.11
uv sync --locked --python 3.11
```

`--locked` prevents rewriting the lockfile; stop and investigate if it reports a mismatch. The lockfile references the Aliyun package mirror. These commands create an environment and may download Python/packages. See [uv project synchronization](https://docs.astral.sh/uv/concepts/projects/sync/) and [Python management](https://docs.astral.sh/uv/concepts/python-versions/).

Create or review a root `.env` locally with the following settings. An `.env` already exists in this checkout; its contents were not read during this review.

```dotenv
DASHVECTOR_API_KEY=<your-key>
DASHVECTOR_ENDPOINT=<your-cluster-endpoint>
DASHSCOPE_API_KEY=<your-key>
DASHSCOPE_BASE_URL=<your-region-specific-openai-compatible-base-url>
LLM_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSION=1024
```

Use matching provider regions and verify the embedding output dimension against the collection. The code configures a 1024-dimensional collection but does not explicitly send a dimension in embedding requests. The current `.gitignore` does not exclude `.env`; keep secrets out of commits and shared logs.

Known startup checks:

- `familyagent/__main__.py` imports `fastapi_cdn_host`, absent from both declared dependencies and the lockfile. A temporary diagnostic command is `uv run --locked --with fastapi-cdn-host python -m familyagent`; it adds a runtime dependency without editing project metadata. This is not a verified complete fix.
- `pydantic_settings` is imported directly but is only a transitive dependency in the lockfile.
- `embedding_func.py` uses `langchain.embeddings.base.Embeddings`; check compatibility with the pinned LangChain 1.2.7. A likely future fix is importing from `langchain_core.embeddings`.
- Modules initialize clients/agents during import, including DashVector collection-list requests. Credentials and network failures can affect startup.

After resolving startup blockers, the normal entry point is:

```powershell
uv run --locked python -m familyagent
```

The module starts Uvicorn on `0.0.0.0:8000` with reload enabled. `FASTAPI_HOST` / `FASTAPI_PORT` settings are currently not used by this entry point. An explicit alternative is `uv run --locked uvicorn familyagent.__main__:app --host 127.0.0.1 --port 8000` (same import/dependency prerequisites).

| URL | Purpose |
| --- | --- |
| `http://127.0.0.1:8000/` | Root JSON, not the chat homepage or a dependency readiness check |
| `http://127.0.0.1:8000/agent/` | Health chat |
| `http://127.0.0.1:8000/agent/travel/` | Travel chat |
| `http://127.0.0.1:8000/agent/dispatch` | Intent-dispatch chat |
| `http://127.0.0.1:8000/docs` | API documentation |

Health and travel stream POST endpoints accept a form field `query` at `/agent/health/stream/` and `/agent/travel/stream/`. Dispatch accepts JSON `{"question":"..."}` at `/agent/dispatch/stream`. Responses use `text/event-stream` but currently yield raw text chunks rather than framed SSE events; the pages consume them using fetch streams.

For a new/empty DashVector collection, the existing ingestion entry point is:

```powershell
uv run --locked python -c "from familyagent.func.vector_db_func import init_vector_db; init_vector_db()"
```

This **writes to remote DashVector** and calls the embedding provider. It uses collection `health_knowledge`, dot-product similarity, default chunks of 200 characters with 30 overlap, and IDs `doc_0`, `doc_1`, etc. Check the target collection before running; repeated inserts are not an idempotent rebuild. Ingestion is separate from starting the web server.

## Next steps

1. Restore a reproducible uv startup and verify ingestion, retrieval, and chat.
2. Improve the existing UI and English support.
3. Execute real tools, then expose and consume them through MCP.
4. Deploy the application locally on Kubernetes; DashVector and model APIs remain external services.
5. Evaluate 100 realistic cases and report measured retrieval quality, tool-call accuracy, and p95 latency.

See [current assessment](plan/ASSESSMENT.md), [implementation roadmap](plan/ROADMAP.md), and [evaluation protocol](plan/EVALUATION.md). The proposed 76% → 88% Recall@3 figures are aspirations, not existing measurements.

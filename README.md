# Chess Agent

[中文说明](README_CN.md)

A chess assistant built with FastAPI + LangChain. It answers questions about chess openings and Lichess puzzles by calling two MCP servers, runs on a local Kubernetes cluster (kind), and is measured on 100 evaluation cases. Results: [EVAL_REPORT.md](EVAL_REPORT.md).

```
browser ──> web (FastAPI + LangChain agent, :8000)
                ├─ MCP (streamable HTTP) ──> mcp-openings (:8001)  SQLite + FTS5 over the Lichess chess-openings dataset (3,704 lines, CC0)
                └─ MCP (streamable HTTP) ──> mcp-lichess  (:8002)  Lichess puzzle API (live) or recorded responses (replay)
```

Tool failures reach the model as `TOOL_ERROR:` text and the prompt requires it to report them instead of inventing data.

## Run locally (Windows, PowerShell)

```powershell
uv sync
.venv\Scripts\activate
copy .env.example .env          # fill in DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL
python -m familyagent.mcp_servers.openings_server    # terminal 1
python -m familyagent.mcp_servers.lichess_server     # terminal 2
python -m familyagent                                 # terminal 3 -> http://127.0.0.1:8000
```

The chat page is English by default with a one-click switch to Chinese.

## Run on Kubernetes (WSL2 + Docker + kind)

```bash
git clone <repo> && cd FamilyAgent
cp /mnt/<drive>/.../FamilyAgent/.env .env            # .env is not in git
docker build -f deploy/Dockerfile -t familyagent:dev .
kind create cluster --config deploy/kind.yaml        # cluster "chess" (use --name kind if yours is the default one)
kind load docker-image familyagent:dev --name chess
kubectl apply -f deploy/k8s/00-namespace.yaml
set -a; source .env; set +a
kubectl -n chess create secret generic llm-credentials \
  --from-literal=DASHSCOPE_API_KEY="$DASHSCOPE_API_KEY" \
  --from-literal=DASHSCOPE_BASE_URL="$DASHSCOPE_BASE_URL" \
  --from-literal=LLM_MODEL="$LLM_MODEL"
kubectl apply -f deploy/k8s/
kubectl -n chess get pods                            # 3 pods, 1/1 Running
kubectl -n chess port-forward svc/web 8000:8000      # then open http://localhost:8000
```

Settings live in `deploy/k8s/10-configmap.yaml` (`SEARCH_IMPL` = `bm25` or `v2`, `LICHESS_MODE` = `live` or `replay`, `EVAL_FAULTS`). After changing them: `kubectl -n chess rollout restart deployment web mcp-openings mcp-lichess`.

## Tests and evaluation

```bash
pytest -q                                              # no network, no key
python scripts/check_api.py                            # one real model call, prints no secrets
python scripts/check_mcp.py                            # MCP servers (start them first)
python eval/run_retrieval.py --impl v2 --cases eval/cases/retrieval.jsonl   # retrieval only, deterministic
```

End to end (cluster up, `LICHESS_MODE=replay`, `EVAL_FAULTS=true`, pods Ready; the runner opens its own port-forwards):

```bash
python eval/run_e2e.py --label v2_a                    # 100 cases, saved to eval/runs/ (not in git)
python eval/report.py eval/runs/e2e_v2_a.json --show-failed
python eval/make_report.py --baseline eval/runs/e2e_baseline.json --v2 eval/runs/e2e_v2_a.json
```

Cases are in `eval/cases/`: `retrieval.jsonl` (frozen, 50), `dev.jsonl` (tuning), `holdout.jsonl` (written after tuning), `tools.jsonl` (30), `failures.jsonl` (20).

## Layout

`familyagent/` app (`agent/`, `openings/`, `lichess/`, `mcp_servers/`, `route/`, `static/`) · `deploy/` Dockerfile, kind and Kubernetes manifests · `eval/` cases, scoring, runners, report · `scripts/` checks and data build · `tests/`.

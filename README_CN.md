# 国际象棋助手 (Chess Agent)

[English](README.md)

基于 FastAPI + LangChain 的国际象棋助手：通过两个 MCP 服务回答开局和 Lichess 谜题问题，部署在本地 Kubernetes（kind）上，并用 100 条用例评测。评测结果见 [EVAL_REPORT.md](EVAL_REPORT.md)。

```
浏览器 ──> web（FastAPI + LangChain agent，:8000）
              ├─ MCP（streamable HTTP）──> mcp-openings（:8001）  Lichess 开局数据集（3,704 条，CC0），SQLite + FTS5
              └─ MCP（streamable HTTP）──> mcp-lichess （:8002）  Lichess 谜题 API（live）或录制响应（replay）
```

工具失败会以 `TOOL_ERROR:` 文本交给模型，提示词要求它如实报告，不得编造数据。

## 本地运行（Windows，PowerShell）

```powershell
uv sync
.venv\Scripts\activate
copy .env.example .env          # 填入 DASHSCOPE_API_KEY、DASHSCOPE_BASE_URL、LLM_MODEL
python -m familyagent.mcp_servers.openings_server    # 终端 1
python -m familyagent.mcp_servers.lichess_server     # 终端 2
python -m familyagent                                 # 终端 3 -> http://127.0.0.1:8000
```

聊天页面默认英文，可一键切换中文。

## 在 Kubernetes 上运行（WSL2 + Docker + kind）

```bash
git clone <仓库地址> && cd FamilyAgent
cp /mnt/<盘符>/.../FamilyAgent/.env .env             # .env 不在 git 里
docker build -f deploy/Dockerfile -t familyagent:dev .
kind create cluster --config deploy/kind.yaml        # 集群名 chess（如果已有默认集群 kind，则后面用 --name kind）
kind load docker-image familyagent:dev --name chess
kubectl apply -f deploy/k8s/00-namespace.yaml
set -a; source .env; set +a
kubectl -n chess create secret generic llm-credentials \
  --from-literal=DASHSCOPE_API_KEY="$DASHSCOPE_API_KEY" \
  --from-literal=DASHSCOPE_BASE_URL="$DASHSCOPE_BASE_URL" \
  --from-literal=LLM_MODEL="$LLM_MODEL"
kubectl apply -f deploy/k8s/
kubectl -n chess get pods                            # 3 个 Pod，1/1 Running
kubectl -n chess port-forward svc/web 8000:8000      # 然后打开 http://localhost:8000
```

配置在 `deploy/k8s/10-configmap.yaml`（`SEARCH_IMPL` 为 `bm25` 或 `v2`，`LICHESS_MODE` 为 `live` 或 `replay`，`EVAL_FAULTS`）。修改后执行：`kubectl -n chess rollout restart deployment web mcp-openings mcp-lichess`。

## 测试与评测

```bash
pytest -q                                              # 不联网，不需要 key
python scripts/check_api.py                            # 一次真实模型调用，不打印密钥
python scripts/check_mcp.py                            # MCP 服务（需先启动）
python eval/run_retrieval.py --impl v2 --cases eval/cases/retrieval.jsonl   # 只测检索，结果确定
```

端到端评测（集群已启动，`LICHESS_MODE=replay`，`EVAL_FAULTS=true`，Pod 都 Ready；脚本自己建 port-forward）：

```bash
python eval/run_e2e.py --label v2_a                    # 100 条，结果存到 eval/runs/（不在 git 里）
python eval/report.py eval/runs/e2e_v2_a.json --show-failed
python eval/make_report.py --baseline eval/runs/e2e_baseline.json --v2 eval/runs/e2e_v2_a.json
```

用例在 `eval/cases/`：`retrieval.jsonl`（冻结集，50 条）、`dev.jsonl`（调参用）、`holdout.jsonl`（调参之后另写）、`tools.jsonl`（30 条）、`failures.jsonl`（20 条）。

## 目录

`familyagent/` 应用（`agent/`、`openings/`、`lichess/`、`mcp_servers/`、`route/`、`static/`）· `deploy/` Dockerfile、kind 和 Kubernetes 清单 · `eval/` 用例、评分、运行与报告脚本 · `scripts/` 检查与数据构建 · `tests/`。

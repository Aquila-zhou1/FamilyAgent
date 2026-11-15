# 国际象棋助手（Chess Agent）

[English](README.md)

基于 FastAPI + LangChain 的国际象棋助手。目标：Agent 通过 MCP 工具回答开局和 Lichess 谜题问题，部署在本地 Kubernetes，并用 100 条用例评估。

**状态：迭代 0（共 7 个迭代）。** 应用可以启动并通过模型对话；工具、MCP、Kubernetes 和评估尚未实现。迭代计划见 `plan/CHESS_ITERATIONS.md`（仅保存在本地，未提交）。

## 环境（Windows，PowerShell）

```powershell
uv sync
.venv\Scripts\activate
copy .env.example .env   # 然后填入密钥和 base URL
```

## 启动

```powershell
python -m familyagent
```

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:8000/agent/chess` | 聊天页面（默认英文，可一键切换中文） |
| `http://127.0.0.1:8000/docs` | API 文档 |
| `http://127.0.0.1:8000/healthz` | 存活检查，不调用模型 |

`POST /agent/chess/stream` 接收 JSON `{"question": "...", "lang": "en"}`，以纯文本流式返回。

## 检查

```powershell
pytest                        # 不需要网络和真实密钥
python scripts/check_api.py   # 一次真实模型调用，不打印密钥
```

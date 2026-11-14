# FamilyAgent

[English](README.md)

这是一个 Python 3.11 + FastAPI 的家庭助手原型：提供健康知识 RAG 问答、结合天气的旅行规划，以及意图识别分发。技术栈包括 LangChain、百炼 OpenAI 兼容接口、DashVector、Jinja2 和通过 CDN 加载的 Vue 3，无需单独构建前端。

## 已有内容

| 模块 | 实际状态 |
| --- | --- |
| 健康 RAG | CSV 读取、递归分块、远程 Embedding、DashVector 检索及 LLM 整理回答；健康路径使用 top 3。 |
| 知识数据 | `familyagent/data/health_knowledge.csv` 只有 4 条中文记录，覆盖儿童、老人、婴儿；属于演示数据，尚未建立来源可信度。 |
| 工具定义 | 已定义 `health_knowledge_search` 和 `get_weather`，创建 LangChain Agent 时注册工具；天气是写死的模拟数据，未知城市返回默认天气。 |
| 网页实际执行 | 健康流式接口手动检索后直接调用 LLM，而且重复检索两次；旅行流式接口直接调用 LLM。两者均未执行已构建 Agent 的工具循环。 |
| 意图分发 | LLM 将问题分为健康、旅行/天气、闲聊，再转发到对应路径。 |
| 前端 | 三个中文聊天页，支持 fetch 流式读取。 |
| 测试 | 以外部服务调试脚本为主；不是完整的自动化评估，部分脚本直接访问网络，`test_config.py` 会打印 API key。 |

尚未实现或证明：MCP、容器化、K8s 部署、100 条评估集、Recall@3 提升、工具调用准确率和 p95 延迟结果。

## 如何继续使用 uv 启动

以下是恢复步骤，**本轮没有执行安装、入库或服务启动**，因此不能保证当前代码直接跑通。

检查时 uv 已安装，但本项目没有 `.venv`；裸 `python` 指向另一个项目。复制项目后应在本机重建虚拟环境，而不是复用复制来的环境。在项目根目录打开 PowerShell：

```powershell
uv --version
uv python install 3.11
uv sync --locked --python 3.11
```

这些命令会创建环境，可能下载 Python 和依赖。`--locked` 防止改写锁文件；如提示锁文件与依赖声明不一致，应先排查。现有锁文件使用阿里云 PyPI 镜像。命令行为参考 [uv 同步文档](https://docs.astral.sh/uv/concepts/projects/sync/)和 [Python 管理文档](https://docs.astral.sh/uv/concepts/python-versions/)。

在根目录本地准备或核对 `.env`。当前已有该文件，本轮没有读取其中内容：

```dotenv
DASHVECTOR_API_KEY=<你的密钥>
DASHVECTOR_ENDPOINT=<集群地址>
DASHSCOPE_API_KEY=<你的密钥>
DASHSCOPE_BASE_URL=<对应地域的OpenAI兼容接口地址>
LLM_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSION=1024
```

模型与服务地域需要匹配。集合默认 1024 维，但 Embedding 请求没有显式传维度，需要核实实际输出。现有 `.gitignore` 未排除 `.env`，不要把密钥提交到版本库或分享日志。

已发现的启动检查点：

- 入口导入 `fastapi_cdn_host`，但依赖声明和锁文件没有它。可以在后续诊断时临时用 `uv run --locked --with fastapi-cdn-host python -m familyagent` 补充运行依赖，不改项目依赖文件；这不是已验证的完整修复。
- 直接导入的 `pydantic_settings` 当前仅靠传递依赖提供。
- `embedding_func.py` 使用旧路径 `langchain.embeddings.base.Embeddings`，需验证与固定的 LangChain 1.2.7 是否兼容；后续可能需要改为 `langchain_core.embeddings`。
- 模块导入时初始化模型、Agent 和 DashVector 客户端，并尝试列出集合；网络和配置会影响启动。

解决阻塞后，原有启动入口是：

```powershell
uv run --locked python -m familyagent
```

它固定监听 `0.0.0.0:8000` 并启用 reload，尚未使用配置里的 `FASTAPI_HOST` / `FASTAPI_PORT`。也可显式执行 `uv run --locked uvicorn familyagent.__main__:app --host 127.0.0.1 --port 8000`，但同样需要先解决导入和依赖问题。

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:8000/` | JSON 导航，不是聊天首页，也不能证明外部依赖正常 |
| `http://127.0.0.1:8000/agent/` | 健康问答 |
| `http://127.0.0.1:8000/agent/travel/` | 旅行规划 |
| `http://127.0.0.1:8000/agent/dispatch` | 意图分发入口 |
| `http://127.0.0.1:8000/docs` | API 文档 |

健康和旅行 POST 接口分别为 `/agent/health/stream/`、`/agent/travel/stream/`，接收表单字段 `query`；分发接口 `/agent/dispatch/stream` 接收 JSON `{"question":"..."}`。虽然响应类型是 `text/event-stream`，当前输出是原始文本块，没有标准 SSE 事件封装。

若云端尚无知识数据，可在后续执行现有入库入口：

```powershell
uv run --locked python -c "from familyagent.func.vector_db_func import init_vector_db; init_vector_db()"
```

这会调用 Embedding 并**写入远程 DashVector**，不是纯本地操作。默认集合为 `health_knowledge`，dot-product 相似度，分块 200 字符、重叠 30 字符，文档 ID 从 `doc_0` 开始。执行前核对目标集合；重复 insert 不是幂等重建。启动 Web 服务不会自动完成入库。

## 后续方向

1. 用 uv 跑通已有项目，验证入库、检索和聊天。
2. 保留现有前端结构，改善视觉和英文适配。
3. 先打通真实工具执行，再通过 MCP 暴露并调用工具。
4. 尝试本地 K8s 部署；模型 API 和 DashVector 仍是云端服务。
5. 建立 100 条真实场景评估，记录 Recall@3、工具调用准确率、p95 延迟和失败处理。

详见 [现状评估](plan/ASSESSMENT.md)、[分阶段计划](plan/ROADMAP.md)、[评估方案](plan/EVALUATION.md)。简历中的 Recall@3 从 76% 到 88% 目前只是期望，不能当作已有结果。

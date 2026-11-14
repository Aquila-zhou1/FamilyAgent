"""健康问答智能体路由模块 - FastAPI 后端路由"""

import os
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from familyagent.func.agent_health import get_health_agent, stream_health_agent

# 初始化路由
router = APIRouter(prefix="/agent", tags=["家庭健康问答智能体"])

# 配置模板目录：指向 familyagent/templates 目录
# 通过 os.path 拼接获取模板目录
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, "..", "templates")

# 初始化 Jinja2 模板
templates = Jinja2Templates(directory=templates_dir)


# 数据模型
class HealthQuery(BaseModel):
    """健康问答请求数据模型"""

    query: str


@router.get("/", response_class=HTMLResponse)
async def health_agent_page(request: Request):
    """
    前端页面接口
    加载 templates/index.html，向页面传递健康 Agent 的运行状态（正常/异常）
    """
    # 检查健康 Agent 运行状态
    agent = get_health_agent()
    status = "正常" if agent is not None else "异常"

    # 渲染模板
    return templates.TemplateResponse(
        "index.html", {"request": request, "agent_status": status}
    )


@router.post("/health/stream/")
async def health_agent_stream(query: Annotated[str, Form()]):
    """
    数据流式接口
    调用 func/agent_health.py 中的流式输出内容
    """
    print("this is health model")
    return StreamingResponse(stream_health_agent(query), media_type="text/event-stream")

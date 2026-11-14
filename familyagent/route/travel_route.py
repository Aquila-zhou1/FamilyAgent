"""旅游规划智能体路由模块 - FastAPI 后端路由"""

import os
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from familyagent.func.agent_travel import get_travel_agent, stream_travel_agent

# 初始化路由
router = APIRouter(prefix="/agent/travel", tags=["家庭旅游规划智能体"])

# 配置模板目录：指向项目根目录下的"templates"目录
# 通过 os.path 拼接获取项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, "..", "templates")

# 初始化 Jinja2 模板
templates = Jinja2Templates(directory=templates_dir)


# 数据模型
class TravelQuery(BaseModel):
    """旅游规划请求数据模型"""

    query: str


@router.get("/", response_class=HTMLResponse)
async def travel_agent_page(request: Request):
    """
    前端页面接口
    加载 templates/travel.html，向页面传递旅游 Agent 的运行状态（正常/异常）
    """
    # 检查旅游 Agent 运行状态
    agent = get_travel_agent()
    status = "正常" if agent is not None else "异常"

    # 渲染模板
    return templates.TemplateResponse(
        "travel.html", {"request": request, "agent_status": status}
    )


@router.post("/stream/")
async def travel_agent_stream(query: Annotated[str, Form()]):
    """
    数据流式接口
    调用 func/agent_travel.py 中的流式输出内容
    """
    print("进入travel model post")
    return StreamingResponse(stream_travel_agent(query), media_type="text/event-stream")

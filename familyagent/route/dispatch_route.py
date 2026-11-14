"""智能体分发路由模块 - 基于意图识别的分发器

根据用户问题的意图，自动分发到对应的智能体处理
"""

import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from familyagent.func.agent_health import stream_health_agent
from familyagent.func.agent_travel import stream_travel_agent
from familyagent.func.intent_recognition import (
    INTENT_HEALTH,
    INTENT_TRAVEL,
    recognize_intent,
)
from familyagent.func.llm_config import get_llm

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 初始化路由
router = APIRouter(prefix="/agent", tags=["智能体分发"])
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, "..", "templates")

# 初始化 Jinja2 模板
templates = Jinja2Templates(directory=templates_dir)


# 数据模型
class Question(BaseModel):
    """用户问题请求模型"""

    question: str


@router.get("/dispatch", response_class=HTMLResponse)
async def travel_agent_page(request: Request):
    """
    前端页面接口
    加载 templates/travel.html，向页面传递旅游 Agent 的运行状态（正常/异常）
    """
    # 检查旅游 Agent 运行状态
    # 渲染模板
    return templates.TemplateResponse(
        "dispatch.html", {"request": request, "agent_status": True}
    )


@router.post("/dispatch/stream", summary="智能体分发接口（基于大模型意图识别）")
async def dispatch_agent(data: Question) -> StreamingResponse:
    """
    智能体分发接口

    根据用户问题的意图，自动分发到对应的智能体处理：
    1. 旅游规划 → 调用旅游规划 Agent
    2. 健康问答 → 调用健康问答 Agent
    3. 其他/闲聊 → 调用通用大语言模型

    Args:
        data: 包含 question 字段的请求体

    Returns:
        StreamingResponse: 流式响应
    """
    question = data.question
    logger.info(f"收到问题：{question}")

    # 第一步：识别意图
    intent = recognize_intent(question)
    logger.info(f"识别意图：{intent}")

    # 第二步：意图分发
    try:
        if intent == INTENT_TRAVEL:
            # 旅游规划 → 调用旅游规划 Agent
            logger.info("分发到旅游规划 Agent")
            return StreamingResponse(
                stream_travel_agent(question), media_type="text/event-stream"
            )

        elif intent == INTENT_HEALTH:
            # 健康问答 → 调用健康问答 Agent
            logger.info("分发到健康问答 Agent")
            return StreamingResponse(
                stream_health_agent(question), media_type="text/event-stream"
            )

        else:
            # 其他/闲聊 → 调用通用大语言模型
            logger.info("分发到通用大语言模型")
            return StreamingResponse(
                _stream_llm_chat(question), media_type="text/event-stream"
            )

    except Exception as ex:
        logger.error(f"处理问题时出错：{ex}")

        # 出错时返回错误信息
        error_message = f"处理失败：{str(ex)}"

        async def error_stream():
            yield error_message

        return StreamingResponse(error_stream(), media_type="text/event-stream")


async def _stream_llm_chat(question: str):
    """
    流式调用通用大语言模型进行闲聊

    Args:
        question: 用户问题

    Yields:
        str: 模型响应片段
    """
    llm = get_llm()
    if llm is None:
        yield "抱歉，服务暂时不可用，请稍后再试。"
        return

    from langchain_core.messages import HumanMessage, SystemMessage

    system_prompt = """你是一个友好、聪明的 AI 助手，可以与用户进行自然对话。
请用简洁、友好的语气回答用户的问题。"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=question),
    ]

    # 使用流式调用
    response = llm.stream(messages)
    for chunk in response:
        if chunk.content:
            yield chunk.content

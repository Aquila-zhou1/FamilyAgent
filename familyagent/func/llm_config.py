"""LLM 配置模块 - 基于 langchain_openai.ChatOpenAI"""

import logging

from langchain_openai import ChatOpenAI

from familyagent.config import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局 LLM 实例
llm: ChatOpenAI | None = None


def init_llm() -> ChatOpenAI | None:
    """
    初始化 LLM 实例

    Returns:
        ChatOpenAI | None: 初始化成功返回 ChatOpenAI 实例，失败返回 None
    """
    global llm

    try:
        llm = ChatOpenAI(
            model=config.LLM_MODEL,
            api_key=config.DASHSCOPE_API_KEY,
            base_url=config.DASHSCOPE_BASE_URL,
        )
        logger.info(f"LLM 初始化成功 - 模型：{config.LLM_MODEL}")
        return llm

    except Exception as e:
        logger.error(f"LLM 初始化失败：{e}")
        llm = None
        return None


# 模块加载时自动初始化
init_llm()


def get_llm() -> ChatOpenAI | None:
    """
    获取 LLM 实例

    Returns:
        ChatOpenAI | None: LLM 实例，如果未初始化则返回 None
    """
    if llm is None:
        logger.warning("LLM 未初始化，尝试重新初始化...")
        return init_llm()
    return llm

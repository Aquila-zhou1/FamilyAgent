"""健康问答智能体模块 - 基于 LangChain 1.2.7 create_agent API"""

import logging
from typing import Generator

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage

from familyagent.func.llm_config import get_llm
from familyagent.func.tool_health import create_health_tool
from familyagent.func.vector_db_func import VectorDBSearcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局健康问答智能体实例
health_agent = None

# 向量库检索器实例
vector_searcher = VectorDBSearcher(collection_name="health_knowledge", top_k=3)

# 系统提示词模板
SYSTEM_PROMPT_TEMPLATE = """你是一个专业的健康问答助手，专注于提供儿童、老人、婴儿的健康护理知识。

回答规则：
1. 优先检索本地向量库中的权威健康知识
2. 如果检索到有效结果，直接整理返回，不要添加额外的 AI 生成内容
3. 如果未检索到相关内容，返回 AI 生成内容，并在开头标注【⚠️ AI 生成内容，仅供参考，请咨询专业医生】
4. 回答简洁专业，仅保留核心信息

可用工具：
- health_knowledge_search: 查询权威健康知识库

请根据用户的健康问题，使用工具检索相关知识后给出专业回答。
"""


def search_knowledge_base(query: str) -> tuple[bool, str]:
    """
    检索向量库中的健康知识

    Args:
        query: 用户查询

    Returns:
        tuple[bool, str]: (是否找到结果，检索结果或空字符串)
    """
    try:
        results = vector_searcher.search(
            query=query,
            output_fields=["content", "title", "category"],
        )

        if not results:
            return False, ""

        # 格式化检索结果
        output_lines = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "未知")
            category = result.get("category", "未知")
            content = result.get("content", "")
            score = result.get("score", 0)

            output_lines.append(f"【{i}】{title}（分类：{category}）")
            output_lines.append(f"匹配度：{score:.4f}")
            output_lines.append(f"处理步骤：{content}")
            output_lines.append("")

        return True, "\n".join(output_lines)

    except Exception as e:
        logger.error(f"检索向量库时出错：{e}")
        return False, ""


def create_health_agent_prompt(query: str) -> list:
    """
    创建健康问答智能体的消息提示

    Args:
        query: 用户查询

    Returns:
        list: 消息列表
    """
    # 先检索向量库
    found, knowledge = search_knowledge_base(query)

    if found:
        # 检索到结果，直接使用检索内容
        system_content = f"""{SYSTEM_PROMPT_TEMPLATE}

已检索到相关健康知识：
{knowledge}

请基于以上检索到的权威知识，整理并回答用户的问题。不要添加检索内容之外的 AI 生成内容。"""
    else:
        # 未检索到结果，使用 AI 生成内容
        system_content = f"""{SYSTEM_PROMPT_TEMPLATE}

【⚠️ AI 生成内容，仅供参考，请咨询专业医生】

未检索到相关健康知识，请基于你的医学知识回答用户问题，并在回答开头添加上述标注。"""

    return [
        SystemMessage(content=system_content),
        HumanMessage(content=query),
    ]


def create_health_agent() -> object | None:
    """
    创建健康问答智能体

    基于 LangChain 1.2.7 create_agent API

    Returns:
        object | None: 智能体实例，创建失败返回 None
    """
    try:
        # 获取 LLM 实例
        llm = get_llm()
        if llm is None:
            logger.error("LLM 未初始化，无法创建智能体")
            return None

        # 创建健康知识检索工具
        tools = [create_health_tool()]

        # 使用 LangChain 1.2.7 create_agent API 创建智能体
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=SYSTEM_PROMPT_TEMPLATE,
        )

        logger.info("健康问答智能体创建成功")
        return agent

    except Exception as e:
        logger.error(f"创建健康问答智能体失败：{e}")
        return None


def init_health_agent() -> object | None:
    """
    初始化全局健康问答智能体实例

    Returns:
        object | None: 智能体实例，初始化失败返回 None
    """
    global health_agent

    try:
        logger.info("开始初始化健康问答智能体...")

        # 创建智能体实例
        health_agent = create_health_agent()

        if health_agent is not None:
            logger.info("健康问答智能体初始化成功")
        else:
            logger.warning("健康问答智能体初始化失败，返回 None")

        return health_agent

    except Exception as e:
        logger.error(f"初始化健康问答智能体时发生异常：{e}")
        health_agent = None
        return None


def get_health_agent() -> object | None:
    """
    获取健康问答智能体实例

    Returns:
        object | None: 智能体实例，未初始化返回 None
    """
    global health_agent

    if health_agent is None:
        logger.warning("智能体未初始化，尝试重新初始化...")
        return init_health_agent()

    return health_agent


def invoke_health_agent(query: str) -> str:
    """
    调用健康问答智能体（非流式）

    Args:
        query: 用户查询

    Returns:
        str: 智能体响应
    """
    try:
        # 先检索向量库
        found, knowledge = search_knowledge_base(query)

        if found:
            # 检索到结果，直接整理返回
            logger.info(f"检索到健康知识，共 {len(knowledge)} 字符")

            # 构建提示词
            messages = create_health_agent_prompt(query)

            # 获取 LLM 实例
            llm = get_llm()
            if llm is None:
                return "LLM 未初始化，无法回答问题"

            # 调用 LLM 整理检索结果
            response = llm.invoke(messages)
            return response.content

        else:
            # 未检索到结果，返回 AI 生成内容
            logger.info("未检索到健康知识，使用 AI 生成内容")

            # 构建带标注的提示词
            messages = create_health_agent_prompt(query)

            # 获取 LLM 实例
            llm = get_llm()
            if llm is None:
                return "LLM 未初始化，无法回答问题"

            # 调用 LLM 生成回答
            response = llm.invoke(messages)
            return response.content

    except Exception as e:
        logger.error(f"调用健康问答智能体时出错：{e}")
        return f"调用智能体时出错：{str(e)}"


def stream_health_agent(query: str) -> Generator[str, None, None]:
    """
    流式调用健康问答智能体

    Args:
        query: 用户查询

    Yields:
        str: 响应文本块
    """
    try:
        # 先检索向量库
        found, knowledge = search_knowledge_base(query)

        # 构建提示词
        messages = create_health_agent_prompt(query)

        # 获取 LLM 实例
        llm = get_llm()
        if llm is None:
            yield "LLM 未初始化，无法回答问题"
            return

        # 流式调用 LLM
        for chunk in llm.stream(messages):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content

    except Exception as e:
        logger.error(f"流式调用健康问答智能体时出错：{e}")
        yield f"流式调用出错：{str(e)}"


# 模块加载时自动初始化
init_health_agent()


# 测试入口
if __name__ == "__main__":
    print("=" * 60)
    print("健康问答智能体测试")
    print("=" * 60)

    # 测试场景 1：向量库有结果
    print("\n【测试场景 1】向量库有结果")
    print("查询：儿童发烧怎么处理")
    print("-" * 40)
    response = invoke_health_agent("儿童发烧怎么处理")
    print(f"响应：{response}")

    # 测试场景 2：向量库无结果
    print("\n" + "=" * 60)
    print("\n【测试场景 2】向量库无结果")
    print("查询：量子纠缠疗法治疗癌症")
    print("-" * 40)
    response = invoke_health_agent("量子纠缠疗法治疗癌症")
    print(f"响应：{response}")

    # 测试场景 3：流式调用
    print("\n" + "=" * 60)
    print("\n【测试场景 3】流式调用")
    print("查询：老人高血压日常护理")
    print("-" * 40)
    print("流式响应：", end="", flush=True)
    for chunk in stream_health_agent("老人高血压日常护理"):
        print(chunk, end="", flush=True)
    print()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

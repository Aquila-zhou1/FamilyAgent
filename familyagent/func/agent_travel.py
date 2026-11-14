"""旅游规划智能体模块 - 基于 LangChain 1.5.1 create_agent API

专为老人 + 儿童设计的 3 天家庭旅游路线规划 Agent
"""

import logging
from typing import Generator

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from familyagent.func.llm_config import get_llm

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局旅游规划 Agent 实例
travel_agent = None

# 系统提示词模板
SYSTEM_PROMPT_TEMPLATE = """你是一个专业的家庭旅游规划师，专为老人和儿童设计 3 天旅游路线。

你的任务：
1. 首先必须调用 get_weather 工具获取目的地未来 3 天的天气信息
2. 根据天气情况，设计舒缓友好的 3 天旅游行程
3. 行程必须包含：
   - 每日景点安排（考虑老人和儿童体力，节奏舒缓）
   - 穿衣建议（根据天气）
   - 休息点推荐
   - 餐饮推荐（适合老人和儿童的餐厅）
   - 交通建议
4. 如果天气不佳，提供室内备选方案

回答格式：
- 先说明天气情况
- 然后给出 3 天详细行程
- 最后提供温馨提示

请用温暖、专业的语气回答。"""


@tool
def get_weather(location: str) -> str:
    """
    获取指定城市未来 3 天的天气预报

    Args:
        location: 城市名称，如"北京"、"上海"

    Returns:
        str: 未来 3 天的详细天气信息
    """
    try:
        # 模拟天气数据（实际项目中可接入真实天气 API）
        weather_data = {
            "北京": [
                {"date": "第 1 天", "weather": "晴", "temp": "18-28°C", "wind": "微风"},
                {
                    "date": "第 2 天",
                    "weather": "多云",
                    "temp": "16-25°C",
                    "wind": "北风 2-3 级",
                },
                {"date": "第 3 天", "weather": "晴", "temp": "17-27°C", "wind": "微风"},
            ],
            "上海": [
                {
                    "date": "第 1 天",
                    "weather": "小雨",
                    "temp": "20-26°C",
                    "wind": "东南风 3-4 级",
                },
                {
                    "date": "第 2 天",
                    "weather": "阴",
                    "temp": "19-24°C",
                    "wind": "东风 2-3 级",
                },
                {
                    "date": "第 3 天",
                    "weather": "多云",
                    "temp": "21-27°C",
                    "wind": "微风",
                },
            ],
            "广州": [
                {
                    "date": "第 1 天",
                    "weather": "雷阵雨",
                    "temp": "24-32°C",
                    "wind": "南风 3-4 级",
                },
                {
                    "date": "第 2 天",
                    "weather": "多云",
                    "temp": "25-33°C",
                    "wind": "微风",
                },
                {"date": "第 3 天", "weather": "晴", "temp": "26-34°C", "wind": "微风"},
            ],
            "深圳": [
                {
                    "date": "第 1 天",
                    "weather": "多云",
                    "temp": "25-32°C",
                    "wind": "微风",
                },
                {"date": "第 2 天", "weather": "晴", "temp": "26-33°C", "wind": "微风"},
                {
                    "date": "第 3 天",
                    "weather": "晴",
                    "temp": "27-34°C",
                    "wind": "南风 2-3 级",
                },
            ],
            "杭州": [
                {
                    "date": "第 1 天",
                    "weather": "阴",
                    "temp": "18-25°C",
                    "wind": "东风 2-3 级",
                },
                {
                    "date": "第 2 天",
                    "weather": "小雨",
                    "temp": "17-23°C",
                    "wind": "北风 3-4 级",
                },
                {
                    "date": "第 3 天",
                    "weather": "多云",
                    "temp": "19-26°C",
                    "wind": "微风",
                },
            ],
            "成都": [
                {"date": "第 1 天", "weather": "阴", "temp": "16-24°C", "wind": "微风"},
                {
                    "date": "第 2 天",
                    "weather": "小雨",
                    "temp": "15-22°C",
                    "wind": "北风 2-3 级",
                },
                {"date": "第 3 天", "weather": "阴", "temp": "16-23°C", "wind": "微风"},
            ],
            "西安": [
                {"date": "第 1 天", "weather": "晴", "temp": "14-26°C", "wind": "微风"},
                {"date": "第 2 天", "weather": "晴", "temp": "15-27°C", "wind": "微风"},
                {
                    "date": "第 3 天",
                    "weather": "多云",
                    "temp": "16-25°C",
                    "wind": "东风 2-3 级",
                },
            ],
        }

        # 默认天气（如果城市不在列表中）
        default_weather = [
            {"date": "第 1 天", "weather": "多云", "temp": "18-26°C", "wind": "微风"},
            {"date": "第 2 天", "weather": "晴", "temp": "19-27°C", "wind": "微风"},
            {"date": "第 3 天", "weather": "晴", "temp": "20-28°C", "wind": "微风"},
        ]

        weather_list = weather_data.get(location, default_weather)

        # 格式化天气信息
        result_lines = [f" {location}未来 3 天天气预报："]
        for day in weather_list:
            result_lines.append(
                f"{day['date']}: {day['weather']}，气温{day['temp']}，{day['wind']}"
            )

        return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"获取天气信息时出错：{e}")
        return f"获取天气信息失败：{str(e)}"


def create_travel_agent_prompt(destination: str, preferences: str = "") -> list:
    """
    创建旅游规划智能体的消息提示

    Args:
        destination: 旅游目的地
        preferences: 用户偏好（可选）

    Returns:
        list: 消息列表
    """
    user_query = f"请为我和家人（有老人和儿童）规划一个{destination}3 天旅游路线"
    if preferences:
        user_query += f"。我们的偏好：{preferences}"

    return [
        SystemMessage(content=SYSTEM_PROMPT_TEMPLATE),
        HumanMessage(content=user_query),
    ]


def create_travel_agent() -> object | None:
    """
    创建旅游规划智能体

    基于 LangChain 1.5.1 create_agent API

    Returns:
        object | None: 智能体实例，创建失败返回 None
    """
    try:
        # 获取 LLM 实例
        llm = get_llm()
        if llm is None:
            logger.error("LLM 未初始化，无法创建智能体")
            return None

        # 创建天气查询工具
        tools = [get_weather]

        # 使用 LangChain 1.5.1 create_agent API 创建智能体
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=SYSTEM_PROMPT_TEMPLATE,
        )

        logger.info("旅游规划智能体创建成功")
        return agent

    except Exception as e:
        logger.error(f"创建旅游规划智能体失败：{e}")
        return None


def init_travel_agent() -> object | None:
    """
    初始化全局旅游规划智能体实例

    Returns:
        object | None: 智能体实例，初始化失败返回 None
    """
    global travel_agent

    try:
        logger.info("开始初始化旅游规划智能体...")

        # 创建智能体实例
        travel_agent = create_travel_agent()

        if travel_agent is not None:
            logger.info("旅游规划智能体初始化成功")
        else:
            logger.warning("旅游规划智能体初始化失败")

        return travel_agent

    except Exception as e:
        logger.error(f"初始化旅游规划智能体时发生异常：{e}")
        travel_agent = None
        return None


def get_travel_agent() -> object | None:
    """
    获取旅游规划智能体实例

    Returns:
        object | None: 智能体实例，未初始化返回 None
    """
    global travel_agent

    if travel_agent is None:
        logger.warning("智能体未初始化，尝试重新初始化...")
        return init_travel_agent()

    return travel_agent


def invoke_travel_agent(destination: str, preferences: str = "") -> str:
    """
    调用旅游规划智能体（非流式）

    Args:
        destination: 旅游目的地
        preferences: 用户偏好（可选）

    Returns:
        str: 智能体响应
    """
    try:
        # 构建提示词
        messages = create_travel_agent_prompt(destination, preferences)

        # 获取 LLM 实例
        llm = get_llm()
        if llm is None:
            return "LLM 未初始化，无法规划行程"

        # 调用 LLM 生成回答
        response = llm.invoke(messages)
        return response.content

    except Exception as e:
        logger.error(f"调用旅游规划智能体时出错：{e}")
        return f"调用智能体时出错：{str(e)}"


def stream_travel_agent(
    destination: str, preferences: str = ""
) -> Generator[str, None, None]:
    """
    流式调用旅游规划智能体

    Args:
        destination: 旅游目的地
        preferences: 用户偏好（可选）

    Yields:
        str: 响应文本块
    """
    try:
        # 构建提示词
        print("destination: ", destination)
        print("preferences: ", preferences)
        messages = create_travel_agent_prompt(destination, preferences)
        print("messages: ", messages)
        # 获取 LLM 实例
        llm = get_llm()
        if llm is None:
            yield "LLM 未初始化，无法规划行程"
            return

        # 流式调用 LLM
        for chunk in llm.stream(messages):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content

    except Exception as e:
        logger.error(f"流式调用旅游规划智能体时出错：{e}")
        yield f"流式调用出错：{str(e)}"


# 模块加载时自动初始化
init_travel_agent()


# 测试入口
if __name__ == "__main__":
    print("=" * 60)
    print("旅游规划智能体测试")
    print("=" * 60)

    # 测试场景 1：北京 3 天旅游规划
    print("\n【测试场景 1】北京 3 天家庭旅游规划")
    print("目的地：北京")
    print("-" * 40)
    response = invoke_travel_agent("北京", "有 70 岁老人和 5 岁儿童")
    print(f"响应：{response}")

    # 测试场景 2：流式调用
    print("\n" + "=" * 60)
    print("\n【测试场景 2】流式调用 - 上海 3 天旅游规划")
    print("目的地：上海")
    print("-" * 40)
    print("流式响应：", end="", flush=True)
    for chunk in stream_travel_agent("上海", "有老人和儿童，喜欢历史文化"):
        print(chunk, end="", flush=True)
    print()

    # 测试场景 3：天气工具测试
    print("\n" + "=" * 60)
    print("\n【测试场景 3】天气工具测试")
    print("-" * 40)
    weather_result = get_weather.invoke("北京")
    print(f"北京天气：{weather_result}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

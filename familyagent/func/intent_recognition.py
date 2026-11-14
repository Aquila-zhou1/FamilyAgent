"""意图识别模块 - 识别用户问题的意图类型

支持三类意图：旅游规划、健康问答、闲聊
"""

import logging
import os
import sys

# 自动将项目根目录添加到 Python 路径，避免导入报错
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from familyagent.func.llm_config import get_llm

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 意图识别的系统提示词
SYSTEM_PROMPT = """你是一个意图识别助手，负责分析用户问题的意图类型。

你只能识别以下三类意图：
1. 旅游规划：与旅游、出行、景点、行程规划、天气查询相关的问题
2. 健康问答：与健康、医疗、疾病、护理、用药、养生相关的问题
3. 闲聊：日常问候、聊天、不涉及上述两类的问题

输出规则：
- 仅返回「旅游规划」「健康问答」「闲聊」三者之一
- 不要返回任何解释、标点符号或其他内容
- 如果无法确定，返回「闲聊」"""

# 意图标签常量
INTENT_TRAVEL = "旅游规划"
INTENT_HEALTH = "健康问答"
INTENT_CHAT = "闲聊"

# 有效的意图标签集合
VALID_INTENTS = {INTENT_TRAVEL, INTENT_HEALTH, INTENT_CHAT}


def recognize_intent(query: str) -> str:
    """
    识别用户问题的意图类型

    Args:
        query: 用户输入的问题

    Returns:
        str: 意图标签，仅返回「旅游规划」「健康问答」「闲聊」三者之一
    """
    try:
        # 获取 LLM 实例
        llm = get_llm()
        if llm is None:
            logger.warning("LLM 未初始化，返回默认意图「闲聊」")
            return INTENT_CHAT

        # 构建消息
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query)]

        # 调用 LLM 进行意图识别
        response = llm.invoke(messages)
        intent = response.content.strip()

        # 验证返回的意图标签是否有效
        if intent in VALID_INTENTS:
            logger.info(f"识别意图：{query[:20]}... -> {intent}")
            return intent
        else:
            # 如果返回的内容不在有效标签中，尝试提取
            for valid_intent in VALID_INTENTS:
                if valid_intent in intent:
                    logger.info(f"识别意图：{query[:20]}... -> {valid_intent}")
                    return valid_intent

            # 无法提取则返回默认意图
            logger.warning(f"无法识别的意图标签：{intent}，返回默认意图「闲聊」")
            return INTENT_CHAT

    except Exception as e:
        # 异常处理：识别出错时默认返回「闲聊」
        logger.error(f"意图识别出错：{e}，返回默认意图「闲聊」")
        return INTENT_CHAT


def batch_recognize_intents(queries: list[str]) -> list[str]:
    """
    批量识别多个问题的意图类型

    Args:
        queries: 问题列表

    Returns:
        list[str]: 意图标签列表
    """
    return [recognize_intent(query) for query in queries]


# 测试入口
if __name__ == "__main__":
    print("=" * 60)
    print("意图识别模块测试")
    print("=" * 60)

    # 测试用例：覆盖旅游规划、健康问答、闲聊三类场景
    test_cases = [
        # 旅游规划类
        ("北京三日游怎么安排？", INTENT_TRAVEL),
        # 健康问答类
        ("儿童发烧怎么处理？", INTENT_HEALTH),
        # 闲聊类
        ("你好，今天心情不错", INTENT_CHAT),
    ]

    print("\n开始测试...\n")

    # 统计结果
    correct_count = 0
    total_count = len(test_cases)

    # 按类别分组统计
    category_stats = {
        INTENT_TRAVEL: {"correct": 0, "total": 0},
        INTENT_HEALTH: {"correct": 0, "total": 0},
        INTENT_CHAT: {"correct": 0, "total": 0},
    }

    for query, expected_intent in test_cases:
        result = recognize_intent(query)
        is_correct = result == expected_intent
        if is_correct:
            correct_count += 1
            category_stats[expected_intent]["correct"] += 1
        category_stats[expected_intent]["total"] += 1

        status = "✓" if is_correct else "✗"
        print(f"{status} 问题：{query}")
        print(f"  预期：{expected_intent} | 结果：{result}\n")

    # 输出统计结果
    print("=" * 60)
    print("测试结果统计")
    print("=" * 60)
    print(
        f"\n总体准确率：{correct_count}/{total_count} = {correct_count / total_count * 100:.1f}%\n"
    )

    for intent, stats in category_stats.items():
        if stats["total"] > 0:
            accuracy = stats["correct"] / stats["total"] * 100
            print(f"{intent}: {stats['correct']}/{stats['total']} = {accuracy:.1f}%")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

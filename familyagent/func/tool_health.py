"""健康知识检索 Tool 工具类 - 基于 LangChain 新版 API"""

from typing import Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from familyagent.func.vector_db_func import VectorDBSearcher


class HealthQueryInput(BaseModel):
    """健康知识查询输入参数模型"""

    query: str = Field(
        description="用户的健康问题，例如'儿童发烧怎么办'、'老人高血压如何护理'"
    )


class HealthKnowledgeTool(BaseTool):
    """
    健康知识检索工具

    功能：查询权威的儿童/老人/婴儿健康护理知识，返回具体处理步骤
    数据源：基于向量数据库检索健康知识库
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    name: str = "health_knowledge_search"
    description: str = (
        "查询权威的儿童、老人、婴儿健康护理知识，返回具体处理步骤。"
        "适用于询问疾病症状、护理方法、急救措施等健康问题。"
    )
    args_schema: type[BaseModel] = HealthQueryInput

    collection_name: str = "health_knowledge"
    top_k: int = 3
    searcher: Optional[VectorDBSearcher] = None

    def model_post_init(self, __context) -> None:
        """模型初始化后处理"""
        if self.searcher is None:
            self.searcher = VectorDBSearcher(
                collection_name=self.collection_name, top_k=self.top_k
            )

    def _run(self, query: str) -> str:
        """
        执行健康知识检索

        Args:
            query: 用户查询的健康问题

        Returns:
            str: 格式化的健康知识结果
        """
        try:
            results = self.searcher.search(
                query=query,
                output_fields=["content", "title", "category"],
            )

            if not results:
                return "未找到相关健康知识，请尝试其他描述方式或咨询专业医生。"

            # 格式化输出结果
            output_lines = []
            output_lines.append(f"为您找到 {len(results)} 条相关健康知识：\n")

            for i, result in enumerate(results, 1):
                title = result.get("title", "未知")
                category = result.get("category", "未知")
                content = result.get("content", "")
                score = result.get("score", 0)

                output_lines.append(f"【{i}】{title}（分类：{category}）")
                output_lines.append(f"匹配度：{score:.4f}")
                output_lines.append(f"处理步骤：{content}")
                output_lines.append("")

            return "\n".join(output_lines)

        except Exception as e:
            return f"检索健康知识时出错：{str(e)}"

    async def _arun(self, query: str) -> str:
        """异步执行健康知识检索（当前实现为同步调用）"""
        return self._run(query)


def create_health_tool(
    collection_name: str = "health_knowledge",
    top_k: int = 3,
) -> HealthKnowledgeTool:
    """
    创建健康知识检索工具的便捷函数

    Args:
        collection_name: DashVector 集合名称
        top_k: 返回结果数量

    Returns:
        HealthKnowledgeTool: 健康知识检索工具实例
    """
    return HealthKnowledgeTool(collection_name=collection_name, top_k=top_k)


# 使用示例
if __name__ == "__main__":
    # 创建工具实例
    tool = create_health_tool(top_k=1)

    # 测试查询
    test_query = "儿童发烧怎么处理"
    result = tool.invoke(test_query)
    print(f"查询：{test_query}")
    print(f"结果：\n{result}")

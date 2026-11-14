from typing import List

from langchain.embeddings.base import Embeddings
from openai import OpenAI

from familyagent.config import config


class AliyunEmbeddings(Embeddings):
    """阿里云百炼嵌入模型类，继承自LangChain的Embeddings基类"""

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None):
        """
        初始化阿里云百炼嵌入模型

        Args:
            model: 嵌入模型名称，默认使用配置文件中的EMBEDDING_MODEL
            api_key: 阿里云百炼API密钥，默认使用配置文件中的DASHSCOPE_API_KEY
            base_url: 阿里云百炼API基础URL，默认使用配置文件中的DASHSCOPE_BASE_URL
        """
        self.model = model or config.EMBEDDING_MODEL
        self.api_key = api_key or config.DASHSCOPE_API_KEY
        self.base_url = base_url or config.DASHSCOPE_BASE_URL

        # 创建OpenAI客户端实例，用于访问阿里云百炼的兼容接口
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def embed_query(self, text: str) -> List[float]:
        """
        对单条文本生成嵌入向量

        Args:
            text: 要生成嵌入向量的文本

        Returns:
            List[float]: 嵌入向量
        """
        response = self.client.embeddings.create(model=self.model, input=text)
        return response.data[0].embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        对文档列表生成嵌入向量

        Args:
            texts: 要生成嵌入向量的文档列表

        Returns:
            List[List[float]]: 嵌入向量列表
        """
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [embedding.embedding for embedding in response.data]


# 创建全局的嵌入模型实例
embedding_model = AliyunEmbeddings()

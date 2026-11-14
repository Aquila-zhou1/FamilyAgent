"""向量库初始化模块 - 基于 LangChain 1.2.7 和阿里云 DashVector"""

import csv
from pathlib import Path
from typing import List, Optional

from dashvector import Client, Doc
from langchain_text_splitters import RecursiveCharacterTextSplitter

from familyagent.config import config
from familyagent.func.embedding_func import embedding_model


class VectorDBInitializer:
    """向量数据库初始化类"""

    def __init__(
        self,
        csv_path: str = "familyagent/data/health_knowledge.csv",
        collection_name: str = "health_knowledge",
        chunk_size: int = 200,
        chunk_overlap: int = 30,
    ):
        """
        初始化向量数据库

        Args:
            csv_path: CSV 文件路径
            collection_name: DashVector 集合名称
            chunk_size: 文本分块大小
            chunk_overlap: 文本分块重叠大小
        """
        self.csv_path = Path(csv_path)
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 初始化 DashVector 客户端
        self.client = Client(
            api_key=config.DASHVECTOR_API_KEY,
            endpoint=config.DASHVECTOR_ENDPOINT if config.DASHVECTOR_ENDPOINT else None,
        )
        print(f"客户端创建成功: {bool(self.client)}")
    
        # 2. 列出所有已存在的集合
        print("\n2. 列出所有集合...")
        try:
            collections = self.client.list()
            print(f"已存在的集合列表: {collections}")
        except Exception as e:
            print(f"列出集合失败: {e}")

        # 初始化文本分块器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n", "。", "！", "？", "；", "，", " "],
            length_function=len,
        )

    def validate_csv(self) -> bool:
        """
        校验 CSV 文件存在性和列完整性

        Returns:
            bool: 校验是否通过
        """
        # 检查文件是否存在
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV 文件不存在：{self.csv_path}")

        # 检查文件是否为空
        if self.csv_path.stat().st_size == 0:
            raise ValueError(f"CSV 文件为空：{self.csv_path}")

        # 检查列完整性
        required_columns = {"title", "category", "content"}
        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError("CSV 文件没有表头")

            actual_columns = set(reader.fieldnames)
            missing_columns = required_columns - actual_columns
            if missing_columns:
                raise ValueError(
                    f"CSV 文件缺少必要的列：{missing_columns}，当前列：{actual_columns}"
                )

        return True

    def read_csv(self) -> List[dict]:
        """
        读取 CSV 文件数据

        Returns:
            List[dict]: 包含 title、category、content 的字典列表
        """
        data = []
        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(
                    {
                        "title": row["title"],
                        "category": row["category"],
                        "content": row["content"],
                    }
                )
        return data

    def split_texts(self, texts: List[str]) -> List[str]:
        """
        使用 LangChain 对文本进行分块

        Args:
            texts: 原始文本列表

        Returns:
            List[str]: 分块后的文本列表
        """
        all_chunks = []
        for text in texts:
            chunks = self.text_splitter.split_text(text)
            all_chunks.extend(chunks)

        print(f"文本分块完成：原始文本数={len(texts)}, 分块后数量={len(all_chunks)}")
        return all_chunks

    def create_collection(self) -> bool:
        """
        创建 DashVector 集合

        Returns:
            bool: 创建是否成功
        """
        try:
            # 尝试创建集合，如果已存在则忽略
            rsp = self.client.create(
                name=self.collection_name,
                dimension=config.EMBEDDING_DIMENSION,
                metric="dotproduct",
            )
            if rsp:
                print(f"集合 '{self.collection_name}' 创建成功")
            else:
                print(f"集合 '{self.collection_name}' 可能已存在")
            return True
        except Exception as e:
            print(f"创建集合时出错：{e}")
            # 如果集合已存在，尝试获取
            collection = self.client.get(self.collection_name)
            if collection:
                print(f"集合 '{self.collection_name}' 已存在，获取成功")
                return True
            raise e

    def get_collection(self):
        """获取集合对象"""
        collection = self.client.get(self.collection_name)
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV 文件不存在：{self.csv_path}")
        if not collection:
            raise ValueError(f"集合 '{self.collection_name}' 不存在")
        return collection

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        对文本进行向量化

        Args:
            texts: 文本列表

        Returns:
            List[List[float]]: 嵌入向量列表
        """
        return embedding_model.embed_documents(texts)

    def insert_docs(
        self, chunks: List[str], metadata_list: Optional[List[dict]] = None
    ):
        """
        将文档插入向量数据库

        Args:
            chunks: 分块后的文本列表
            metadata_list: 可选的元数据列表，包含 title、category 等信息
        """
        # 确保集合存在（如果之前未创建或创建失败）
        self.create_collection()
        collection = self.get_collection()

        # 生成嵌入向量
        embeddings = self.embed_texts(chunks)

        # 准备文档列表
        docs = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # 生成唯一 ID
            doc_id = f"doc_{i}"

            # 准备元数据
            fields = {"content": chunk}
            if metadata_list and i < len(metadata_list):
                fields.update(metadata_list[i])

            docs.append(Doc(id=doc_id, vector=embedding, fields=fields))

        # 批量插入
        batch_size = 10
        for i in range(0, len(docs), batch_size):
            batch_docs = docs[i : i + batch_size]
            rsp = collection.insert(batch_docs)
            if rsp:
                print(f"已插入文档 {min(i + batch_size, len(docs))}/{len(docs)}")
            else:
                print(f"插入文档失败：{rsp}")

    def initialize(self):
        """
        执行完整的初始化流程
        """
        print("=" * 50)
        print("开始向量库初始化...")
        print("=" * 50)

        # 1. 校验 CSV 文件
        print("\n[1/5] 校验 CSV 文件...")
        self.validate_csv()
        print("CSV 文件校验通过")

        # 2. 读取 CSV 数据
        print("\n[2/5] 读取 CSV 数据...")
        data = self.read_csv()
        print(f"读取到 {len(data)} 条记录")

        # 3. 文本分块
        print("\n[3/5] 文本分块...")
        contents = [item["content"] for item in data]
        chunks = self.split_texts(contents)

        # 准备元数据（需要与 chunks 对应）
        metadata_list = []
        chunk_index = 0
        for item in data:
            item_chunks = self.text_splitter.split_text(item["content"])
            for _ in item_chunks:
                metadata_list.append(
                    {"title": item["title"], "category": item["category"]}
                )

        # 4. 创建集合
        print("\n[4/5] 创建/获取 DashVector 集合...")
        self.create_collection()

        # 5. 插入文档
        print("\n[5/5] 向量化并插入文档...")
        self.insert_docs(chunks, metadata_list)

        print("\n" + "=" * 50)
        print("向量库初始化完成！")
        print(f"集合名称：{self.collection_name}")
        print(f"分块数量：{len(chunks)}")
        print("=" * 50)


class VectorDBSearcher:
    """向量数据库检索类"""

    def __init__(self, collection_name: str = "health_knowledge", top_k: int = 5):
        """
        初始化检索器

        Args:
            collection_name: DashVector 集合名称
            top_k: 返回最相似结果的数量
        """
        self.collection_name = collection_name
        self.top_k = top_k

        # 初始化 DashVector 客户端
        self.client = Client(
            api_key=config.DASHVECTOR_API_KEY,
            endpoint=config.DASHVECTOR_ENDPOINT if config.DASHVECTOR_ENDPOINT else None,
        )
        print(f"客户端创建成功: {bool(self.client)}")
    
        # 2. 列出所有已存在的集合
        print("\n2. 列出所有集合...")
        try:
            collections = self.client.list()
            print(f"已存在的集合列表: {collections}")
        except Exception as e:
            print(f"列出集合失败: {e}")

    def get_collection(self):
        """获取集合对象"""
        collection = self.client.get(self.collection_name)
        if not collection:
            raise ValueError(f"集合 '{self.collection_name}' 不存在")
        return collection

    def search(
        self, query: str, output_fields: Optional[List[str]] = None
    ) -> List[dict]:
        """
        执行向量检索

        Args:
            query: 查询文本
            output_fields: 需要返回的字段列表

        Returns:
            List[dict]: 检索结果列表
        """
        collection = self.get_collection()

        # 对查询文本进行向量化
        query_embedding = embedding_model.embed_query(query)

        # 执行检索
        if output_fields is None:
            output_fields = ["content", "title", "category"]

        rsp = collection.query(
            vector=query_embedding,
            topk=self.top_k,
            output_fields=output_fields,
        )

        # 解析结果
        results = []
        for doc in rsp.output:
            result = {
                "id": doc.id,
                "score": doc.score,
            }
            if doc.fields:
                result.update(doc.fields)
            results.append(result)

        return results

    def search_with_filter(
        self,
        query: str,
        filter_expr: str = "",
        output_fields: Optional[List[str]] = None,
    ) -> List[dict]:
        """
        执行带过滤条件的向量检索

        Args:
            query: 查询文本
            filter_expr: 过滤表达式，如 "category='儿童健康'"
            output_fields: 需要返回的字段列表

        Returns:
            List[dict]: 检索结果列表
        """
        collection = self.get_collection()

        # 对查询文本进行向量化
        query_embedding = embedding_model.embed_query(query)

        # 执行带过滤的检索
        if output_fields is None:
            output_fields = ["content", "title", "category"]

        rsp = collection.query(
            vector=query_embedding,
            topk=self.top_k,
            output_fields=output_fields,
            filter=filter_expr if filter_expr else None,
        )

        # 解析结果
        results = []
        for doc in rsp.output:
            result = {
                "id": doc.id,
                "score": doc.score,
            }
            if doc.fields:
                result.update(doc.fields)
            results.append(result)

        return results


# 便捷函数
def init_vector_db(
    csv_path: str = None,
    collection_name: str = "health_knowledge",
    chunk_size: int = 200,
    chunk_overlap: int = 30,
) -> VectorDBInitializer:
    """
    初始化向量数据库的便捷函数

    Args:
        csv_path: CSV 文件路径，默认为 familyagent/data/health_knowledge.csv
        collection_name: 集合名称
        chunk_size: 分块大小
        chunk_overlap: 分块重叠大小

    Returns:
        VectorDBInitializer: 初始化器实例
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "data" / "health_knowledge.csv")

    initializer = VectorDBInitializer(
        csv_path=csv_path,
        collection_name=collection_name,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    initializer.initialize()
    return initializer


def search_vector_db(
    query: str,
    collection_name: str = "health_knowledge",
    top_k: int = 1,
) -> List[dict]:
    """
    检索向量数据库的便捷函数

    Args:
        query: 查询文本
        collection_name: 集合名称
        top_k: 返回结果数量

    Returns:
        List[dict]: 检索结果列表
    """
    searcher = VectorDBSearcher(collection_name=collection_name, top_k=top_k)
    return searcher.search(query)


# 主函数示例
if __name__ == "__main__":
    # 初始化向量数据库
    init_vector_db()

    # 测试检索
    results = search_vector_db("儿童发烧怎么办", top_k=3)
    print("\n检索结果：")
    for i, result in enumerate(results, 1):
        print(f"{i}. 标题：{result.get('title', 'N/A')}")
        print(f"   相似度：{result.get('score', 0):.4f}")
        print(f"   内容：{result.get('content', '')[:100]}...")
        print()

# test_collection.py
import dashvector
from dashvector import Client
from familyagent.config import Config # 或者你的配置文件
config = Config()

def debug_collection():
    print("=== DashVector 集合调试 ===")
    
    # 1. 检查客户端连接
    print("\n1. 创建客户端...")
    client = Client(
        api_key=config.DASHVECTOR_API_KEY,
        endpoint=config.DASHVECTOR_ENDPOINT if config.DASHVECTOR_ENDPOINT else None,
    )
    print(f"客户端创建成功: {bool(client)}")
    
    # 2. 列出所有已存在的集合
    print("\n2. 列出所有集合...")
    try:
        collections = client.list()
        print(f"已存在的集合列表: {collections}")
    except Exception as e:
        print(f"列出集合失败: {e}")
    
    # 3. 测试创建集合
    collection_name = "health_knowledge"  # 用测试名称
    print(f"\n3. 尝试创建测试集合 '{collection_name}'...")
    try:
        rsp = client.create(
            name=collection_name,
            dimension=config.EMBEDDING_DIMENSION,
            metric="dotproduct",
        )
        print(f"创建集合响应: {rsp}")
    except Exception as e:
        print(f"创建集合出错: {e}")
    
    # 4. 尝试获取集合
    print(f"\n4. 尝试获取集合 '{collection_name}'...")
    try:
        collection = client.get(collection_name)
        print(f"获取集合结果: {'成功' if collection else '失败'}")
        if collection:
            print(f"集合信息: {collection}")
    except Exception as e:
        print(f"获取集合出错: {e}")

if __name__ == "__main__":
    debug_collection()
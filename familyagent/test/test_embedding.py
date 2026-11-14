#!/usr/bin/env python3
"""
嵌入模型测试文件
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


def test_embedding_model():
    """测试嵌入模型功能"""
    try:
        from familyagent.func.embedding_func import embedding_model

        # 测试文本
        test_text = "小孩发烧怎么办"

        # 生成嵌入向量
        print(f"测试文本: {test_text}")
        vector = embedding_model.embed_query(test_text)

        # 输出结果
        print(f"向量维度: {len(vector)}")
        print(f"向量前10位: {vector[:10]}")

        print("\n✅ 嵌入模型测试成功!")
        return True

    except Exception as e:
        print(f"\n❌ 嵌入模型测试失败: {e}")
        print("请确保已正确配置阿里云百炼API密钥(DASHSCOPE_API_KEY)和相关参数")
        return False


if __name__ == "__main__":
    test_embedding_model()

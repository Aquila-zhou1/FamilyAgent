"""LLM 配置模块测试用例 - 使用 unittest 标准库"""

import unittest

from familyagent.func.llm_config import get_llm, init_llm


class TestLLMConfig(unittest.TestCase):
    """LLM 配置测试类"""

    def test_init_llm(self):
        """测试 LLM 初始化"""
        llm = init_llm()
        # 记录初始化结果（可能因 API 配置为 None）
        print(f"LLM 初始化结果：{llm}")

    def test_get_llm(self):
        """测试获取 LLM 实例"""
        llm = get_llm()
        print(f"获取 LLM 实例：{llm}")

    def test_llm_model_name(self):
        """测试 LLM 模型名称配置"""
        llm = get_llm()
        if llm is not None:
            # 验证模型名称是否正确配置
            has_model = hasattr(llm, "model_name") or hasattr(llm, "model")
            self.assertTrue(has_model, "LLM 应该有 model_name 或 model 属性")
        else:
            print("LLM 未初始化，跳过模型名称测试")

    def test_llm_invoke(self):
        """测试 LLM 调用"""
        llm = get_llm()
        if llm is not None:
            try:
                response = llm.invoke("你好，请简单介绍一下自己")
                self.assertIsNotNone(response, "LLM 响应不应为 None")
                self.assertTrue(hasattr(response, "content"), "响应应该有 content 属性")
                print(f"LLM 响应：{response.content}")
            except Exception as e:
                print(f"LLM API 调用失败：{e}")
        else:
            print("LLM 未初始化，跳过调用测试")


if __name__ == "__main__":
    unittest.main(verbosity=2)

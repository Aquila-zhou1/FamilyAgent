import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config import config

print("阿里云百炼配置:")
print(f"  API_KEY: {config.DASHSCOPE_API_KEY}")
print(f"  BASE_URL: {config.DASHSCOPE_BASE_URL}")

print("\n大语言模型配置:")
print(f"  模型名称: {config.LLM_MODEL}")

print("\n嵌入模型配置:")
print(f"  模型名称: {config.EMBEDDING_MODEL}")
print(f"  向量维度: {config.EMBEDDING_DIMENSION}")

print("\nFastAPI 服务配置:")
print(f"  主机地址: {config.FASTAPI_HOST}")
print(f"  端口号: {config.FASTAPI_PORT}")

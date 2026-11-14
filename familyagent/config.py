from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    DASHVECTOR_API_KEY: str
    DASHVECTOR_ENDPOINT: str
    DASHSCOPE_API_KEY: str
    DASHSCOPE_BASE_URL: str
    LLM_MODEL: str = "qwen-plus"
    FASTAPI_HOST: str = "0.0.0.0"
    FASTAPI_PORT: int = 8000
    EMBEDDING_MODEL: str = "text-embedding-v4"
    CHUNK_SIZE: int = 200
    CHUNK_OVERLAP: int = 30
    VECTOR_DB_PATH: str = "./data/vector_db/health_knowledge"
    DATA_FILE_PATH: str = "./data/health_knowledge.csv"
    SEPARATOR: str = "；"
    EMBEDDING_DIMENSION: int = 1024

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


config = Config()

"""Application settings, read from the environment or a root-level .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    DASHSCOPE_API_KEY: str
    DASHSCOPE_BASE_URL: str
    LLM_MODEL: str = "qwen-plus"
    LLM_TIMEOUT_SECONDS: float = 60.0

    FASTAPI_HOST: str = "0.0.0.0"
    FASTAPI_PORT: int = 8000
    FASTAPI_RELOAD: bool = False

    # extra="ignore": old keys left in .env (e.g. DASHVECTOR_*) must not break startup.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


config = Config()

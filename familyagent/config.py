"""Application settings, read from the environment or a root-level .env file.

One settings class serves all three processes (web app and two MCP servers).
The model credentials are only needed by the web app, so they default to
empty and are checked where the model is created.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Config(BaseSettings):
    # Model (web app only)
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = ""
    LLM_MODEL: str = "qwen-plus"
    LLM_TIMEOUT_SECONDS: float = 60.0

    # Web app
    FASTAPI_HOST: str = "0.0.0.0"
    FASTAPI_PORT: int = 8000
    FASTAPI_RELOAD: bool = False

    # Where the web app finds the MCP servers
    MCP_OPENINGS_URL: str = "http://127.0.0.1:8001/mcp"
    MCP_LICHESS_URL: str = "http://127.0.0.1:8002/mcp"
    MCP_CONNECT_TIMEOUT_SECONDS: float = 5.0
    MCP_CALL_TIMEOUT_SECONDS: float = 15.0
    AGENT_MAX_STEPS: int = 12

    # MCP servers (bind address; Kubernetes sets MCP_HOST=0.0.0.0)
    MCP_HOST: str = "127.0.0.1"
    MCP_OPENINGS_PORT: int = 8001
    MCP_LICHESS_PORT: int = 8002

    # Openings server: which retrieval implementation search_openings uses
    SEARCH_IMPL: str = "bm25"

    # Lichess server
    LICHESS_MODE: str = "live"  # "live" or "replay"
    LICHESS_RECORD: bool = False  # live mode: save responses as fixtures
    LICHESS_TIMEOUT_SECONDS: float = 5.0
    LICHESS_FIXTURES_DIR: str = str(ROOT / "eval" / "fixtures" / "lichess")

    # extra="ignore": old keys left in .env (e.g. DASHVECTOR_*) must not break startup.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


config = Config()

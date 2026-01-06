import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "DouDouChat Server"
    API_STR: str = "/api"

    # Database
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    SQLALCHEMY_DATABASE_URI: str = f"sqlite:///{os.path.join(DATA_DIR, 'doudou.db')}"

    # Memobase SDK Configuration
    MEMOBASE_DB_URL: str = f"sqlite:///{os.path.join(DATA_DIR, 'memobase.db')}"
    MEMOBASE_LLM_API_KEY: str = ""  # Required: Set via environment variable
    MEMOBASE_LLM_BASE_URL: str | None = None
    MEMOBASE_BEST_LLM_MODEL: str = "gpt-4o-mini"
    
    MEMOBASE_ENABLE_EVENT_EMBEDDING: bool = True
    MEMOBASE_EMBEDDING_PROVIDER: str = "openai"
    MEMOBASE_EMBEDDING_API_KEY: str | None = None
    MEMOBASE_EMBEDDING_BASE_URL: str | None = None
    MEMOBASE_EMBEDDING_MODEL: str = "text-embedding-3-small"
    MEMOBASE_EMBEDDING_DIM: int = 1536

    class Config:
        case_sensitive = True

settings = Settings()

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "DouDouChat Server"
    API_STR: str = "/api"

    # Database
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    SQLALCHEMY_DATABASE_URI: str = f"sqlite:///{os.path.join(DATA_DIR, 'doudou.db')}"

    class Config:
        case_sensitive = True

settings = Settings()

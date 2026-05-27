from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "diag_analysis"

    # JWT Authentication
    jwt_secret_key: str = "change-this-to-a-random-64-character-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # AI Providers
    openai_api_key: str = ""
    openai_api_url: str = ""
    ai_model: str = "gpt-4-turbo"
    ai_temperature: float = 0.7
    gemini_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Factory Config - 厂区配置 YAML 文件路径
    factories_yaml_path: str = ""

    # Knowledge Base - 文件存储路径
    knowledge_base_storage_path: str = "./data/knowledge_base"

    # RAGFlow - 知识库引擎
    ragflow_api_url: str = ""
    ragflow_api_key: str = ""
    ragflow_default_dataset: str = "weaveeye-knowledge-base"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
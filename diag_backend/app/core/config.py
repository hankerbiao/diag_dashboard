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
    gemini_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Sync Module - 三方数据同步配置
    sync_api_base_url: str = "http://10.2.68.103"
    sync_api_timeout: int = 30          # 单次请求超时秒数
    sync_max_concurrency: int = 5       # 同时请求 API 2 的最大并发数
    sync_max_retries: int = 3           # 单次请求最大重试次数

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
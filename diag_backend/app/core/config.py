from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os


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

    # Logging
    log_level: str = "INFO"  # DEBUG/INFO/WARNING/ERROR
    log_format: str = "console"  # console/json
    log_file: Optional[str] = None  # 日志文件路径，None 则仅输出控制台
    log_max_bytes: int = 50 * 1024 * 1024  # 50MB 轮转
    log_backup_count: int = 30  # 保留 30 个备份
    log_json: bool = False  # 是否输出 JSON 格式
    log_sql: bool = False  # 是否记录 SQL 查询（DEBUG 级别）

    @property
    def log_dir(self) -> Optional[str]:
        """获取日志目录路径"""
        if self.log_file:
            return os.path.dirname(os.path.abspath(self.log_file))
        return None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

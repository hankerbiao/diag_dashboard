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

    # OA SSO
    oa_jwt_secret: str = ""
    oa_app_name: str = "diagweaveeye"
    oa_login_base_url: str = "http://tl.cooacloud.com/springboard_v3/login_proxy"

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
    ragflow_troubleshooting_dataset: str = "weaveeye-troubleshooting"
    ragflow_repair_case_dataset: str = "weaveeye-repair-cases"
    ragflow_operation_guide_dataset: str = "weaveeye-operation-guides"
    ragflow_faq_dataset: str = "weaveeye-faq"

    # MES API
    mes_request_timeout: int = 30  # MES 实时查询超时秒数

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


def validate_auth_settings(settings: Settings) -> None:
    insecure_jwt_secrets = {
        "",
        "change-this-to-a-random-64-character-string",
    }
    if settings.jwt_secret_key in insecure_jwt_secrets or len(settings.jwt_secret_key) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 characters")
    if not settings.oa_jwt_secret:
        raise RuntimeError("OA_JWT_SECRET must be configured")

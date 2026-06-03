"""
MongoDB 索引初始化 - 应用启动时自动创建必要的索引
"""
import logging
from ..core.utils import utc_now_iso

from motor.motor_asyncio import AsyncIOMotorDatabase

from .factory_config import load_factories_from_yaml

logger = logging.getLogger(__name__)

SNAPSHOT_COLLECTION = "analytics_snapshots"


async def _ensure_sync_server_sn_index(db: AsyncIOMotorDatabase) -> None:
    """Ensure server_sn index is non-unique; only drop legacy unique index when needed."""
    col = db["sync_remote_servers"]
    indexes = await col.index_information()
    existing = indexes.get("idx_sync_servers_sn")
    if existing and existing.get("unique"):
        logger.info("Migrating idx_sync_servers_sn: dropping legacy unique index")
        await col.drop_index("idx_sync_servers_sn")
    await col.create_index("server_sn", name="idx_sync_servers_sn")


async def ensure_indexes(db: AsyncIOMotorDatabase):
    """确保所有集合的必要索引存在（幂等操作）"""

    # ---- users ----
    await db["users"].create_index("email", unique=True, name="idx_users_email")

    # ---- app_settings ----
    await db["app_settings"].create_index("user_id", unique=True, name="idx_app_settings_user_id")

    # ---- devices ----
    await db["devices"].create_index("sn", unique=True, name="idx_devices_sn")

    # ---- error_logs ----
    await db["error_logs"].create_index(
        [("device_id", 1), ("test_time", -1)], name="idx_error_logs_device_test"
    )

    # ---- maintenance_records ----
    await db["maintenance_records"].create_index(
        [("device_id", 1), ("date", -1)], name="idx_maintenance_device_date"
    )

    # ---- case_library ----
    await db["case_library"].create_index("error_code", name="idx_case_library_error_code")
    await db["case_library"].create_index(
        [("root_cause", "text")], name="idx_case_library_root_cause_text"
    )

    # ---- sync_jobs ----
    await db["sync_jobs"].create_index(
        [("factory_id", 1), ("started_at", -1)], name="idx_sync_jobs_factory_started"
    )
    await db["sync_jobs"].create_index(
        [("status", 1), ("started_at", -1)], name="idx_sync_jobs_status_started"
    )
    await db["sync_jobs"].create_index("started_at", name="idx_sync_jobs_started_at")

    # ---- sync_remote_servers ----
    await _ensure_sync_server_sn_index(db)
    await db["sync_remote_servers"].create_index(
        [("factory_id", 1), ("server_sn", 1)], unique=True, name="idx_sync_servers_factory_sn"
    )
    await db["sync_remote_servers"].create_index("synced_at", name="idx_sync_servers_synced_at")
    await db["sync_remote_servers"].create_index(
        "product_models", name="idx_sync_servers_product_models"
    )

    # ---- sync_remote_test_details ----
    await db["sync_remote_test_details"].create_index(
        [("factory_id", 1), ("server_id", 1), ("detailed_flow", 1), ("test_time", 1)],
        name="idx_sync_details_factory_server_flow_time"
    )
    await db["sync_remote_test_details"].create_index(
        [("factory_id", 1), ("server_sn", 1), ("test_time", -1)], name="idx_sync_details_factory_sn_time"
    )

    # ---- analytics 聚合索引 ----
    await db["sync_remote_test_details"].create_index(
        [("test_time", -1)], name="idx_analytics_test_time"
    )
    await db["sync_remote_test_details"].create_index(
        [("fault_type1", 1), ("test_time", 1)], name="idx_analytics_fault_type1_time"
    )
    await db["sync_remote_test_details"].create_index(
        [("server_test_result", 1), ("test_time", 1)], name="idx_analytics_result_time"
    )
    await db["sync_remote_test_details"].create_index(
        [("detailed_flow", 1), ("server_test_result", 1)], name="idx_analytics_flow_result"
    )

    # ---- factory_sites ----
    await db["factory_sites"].create_index("factory_id", unique=True, name="idx_factory_sites_id")

    # ---- auto_sync_configs ----
    await db[SNAPSHOT_COLLECTION].create_index(
        "computed_at", name="idx_analytics_snapshots_computed"
    )

    # ---- diagnosis_cache ----
    await db["diagnosis_cache"].create_index(
        "error_log_id", unique=True, name="idx_diagnosis_cache_error_log_id"
    )

    # ---- diagnosis_sn_history ----
    await db["diagnosis_sn_history"].create_index(
        "sn", name="idx_diagnosis_sn_history_sn"
    )
    await db["diagnosis_sn_history"].create_index(
        [("sn", 1), ("created_at", -1)], name="idx_diagnosis_sn_history_sn_time"
    )
    await db["diagnosis_sn_history"].create_index(
        [("user_id", 1), ("created_at", -1)], name="idx_diagnosis_sn_history_user_time"
    )

    # ---- knowledge_documents ----
    await db["knowledge_documents"].create_index(
        "uploaded_at", name="idx_knowledge_docs_uploaded"
    )
    await db["knowledge_documents"].create_index(
        "title", name="idx_knowledge_docs_title"
    )

    # ---- global_app_config ----
    await db["global_app_config"].create_index("_id", name="idx_global_config_id")

    logger.info("MongoDB indexes ensured successfully")


async def seed_default_data(db: AsyncIOMotorDatabase):
    """首次部署时写入默认厂区等种子数据（幂等）。数据同步见 scripts/weaveeye_sync.py。"""
    now = utc_now_iso()

    # 从 YAML 配置读取厂区列表（单一数据源）
    try:
        factories = load_factories_from_yaml()
    except Exception as e:
        logger.warning("无法加载厂区 YAML 配置: %s，跳过 seed", e)
        return

    for site in factories:
        await db["factory_sites"].update_one(
            {"factory_id": site["factory_id"]},
            {"$setOnInsert": {**site, "created_at": now, "updated_at": now}},
            upsert=True
        )

    # Seed global AI config from environment variables (first deploy only)
    await seed_global_ai_config(db)

    logger.info("Default seed data ensured")


async def seed_global_ai_config(db: AsyncIOMotorDatabase):
    """从环境变量播种全局 AI 配置（首次部署时）"""
    from .config import get_settings
    env_settings = get_settings()
    await db["global_app_config"].update_one(
        {"_id": "ai_config"},
        {"$setOnInsert": {
            "_id": "ai_config",
            "api_key": env_settings.openai_api_key or "",
            "base_url": env_settings.openai_api_url or "https://api.openai.com/v1",
            "model": env_settings.ai_model or "gpt-4-turbo",
            "temperature": env_settings.ai_temperature or 0.7,
            "provider": "openai",
            "updated_by": "system",
            "updated_at": utc_now_iso(),
        }},
        upsert=True
    )

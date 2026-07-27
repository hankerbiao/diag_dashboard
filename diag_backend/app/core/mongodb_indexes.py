"""
MongoDB 索引初始化 - 应用启动时自动创建必要的索引
"""
import logging
from ..core.utils import utc_now_iso

from motor.motor_asyncio import AsyncIOMotorDatabase

from .factory_config import load_factories_from_yaml

logger = logging.getLogger(__name__)



async def ensure_indexes(db: AsyncIOMotorDatabase):
    """确保所有集合的必要索引存在（幂等操作）"""

    # ---- users ----
    # Remove the legacy password-login index. OA users are keyed by itcode;
    # sparse keeps historical local-account documents valid during migration.
    user_indexes = await db["users"].index_information()
    for index_name, index_info in user_indexes.items():
        if index_info.get("key") == [("email", 1)] and index_info.get("unique"):
            await db["users"].drop_index(index_name)
    has_itcode_index = any(
        index_info.get("key") == [("itcode", 1)]
        and index_info.get("unique")
        and index_info.get("sparse")
        for index_info in user_indexes.values()
    )
    if not has_itcode_index:
        await db["users"].create_index(
            "itcode", unique=True, sparse=True, name="idx_users_itcode"
        )
    await db["users"].create_index("created_at", name="idx_users_created_at")
    await db["users"].create_index("last_login_at", name="idx_users_last_login_at")

    # ---- usage_events ----
    await db["usage_events"].create_index(
        "created_at", name="idx_usage_events_created_at"
    )
    await db["usage_events"].create_index(
        [("user_id", 1), ("created_at", -1)], name="idx_usage_events_user_time"
    )
    await db["usage_events"].create_index(
        [("feature", 1), ("created_at", -1)], name="idx_usage_events_feature_time"
    )

    # OA assertion hashes are inserted once and expire with the upstream token.
    await db["oa_login_assertions"].create_index(
        "expires_at", expireAfterSeconds=0, name="idx_oa_assertions_expiry"
    )

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

    # ---- factory_sites ----
    await db["factory_sites"].create_index("factory_id", unique=True, name="idx_factory_sites_id")

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
    await db["knowledge_documents"].create_index(
        [("user_id", 1), ("uploaded_at", -1)], name="idx_knowledge_docs_user_time"
    )

    # ---- test_stats_daily (预计算统计摘要) ----
    await db["test_stats_daily"].create_index(
        [("factory_id", 1), ("date", -1)],
        name="idx_stats_daily_factory_date",
    )
    # ---- _computed_meta (增量计算进度追踪) ----
    await db["_computed_meta"].create_index(
        [("collection", 1), ("factory_id", 1)],
        name="idx_computed_meta_collection_factory",
        unique=True,
    )

    # ---- global_app_config ----
    await db["global_app_config"].create_index("_id", name="idx_global_config_id")

    # ---- log_extraction_prompts (按机型配置的 AI 错误日志提取 prompt) ----
    await db["log_extraction_prompts"].create_index("_id", name="idx_log_extraction_prompts_id")

    # ---- diagnosis_feedback ----
    await db["diagnosis_feedback"].create_index(
        [("history_id", 1)], name="idx_diagnosis_feedback_history"
    )
    await db["diagnosis_feedback"].create_index(
        [("sn", 1), ("factory", 1)], name="idx_diagnosis_feedback_sn_factory"
    )
    await db["diagnosis_feedback"].create_index(
        [("user_id", 1), ("created_at", -1)], name="idx_diagnosis_feedback_user_time"
    )
    await db["diagnosis_feedback"].create_index(
        "rating", name="idx_diagnosis_feedback_rating"
    )
    await db["diagnosis_feedback"].create_index(
        [("factory", 1), ("status", 1), ("created_at", -1)],
        name="idx_diagnosis_feedback_management",
    )

    logger.info("MongoDB indexes ensured successfully")


async def seed_default_data(db: AsyncIOMotorDatabase):
    """首次部署时写入默认厂区等种子数据（幂等）。"""
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

    # Seed 默认错误日志提取 prompt（首次部署，可被前端覆盖）
    await seed_log_extraction_default(db)

    logger.info("Default seed data ensured")


async def seed_global_ai_config(db: AsyncIOMotorDatabase):
    """播种全局 AI 配置（首次部署时插入空配置，由前端配置）"""
    await db["global_app_config"].update_one(
        {"_id": "ai_config"},
        {"$setOnInsert": {
            "_id": "ai_config",
            "api_key": "",
            "base_url": "",
            "model": "",
            "provider": "",
            "updated_by": "system",
            "updated_at": utc_now_iso(),
        }},
        upsert=True
    )


async def seed_log_extraction_default(db: AsyncIOMotorDatabase):
    """播种默认错误日志提取 prompt（首次部署时插入，供前端编辑与机型回退）"""
    from ..services.log_extractor import (
        LOG_EXTRACTION_SYSTEM_PROMPT,
        LOG_EXTRACTION_USER_PROMPT_TPL,
    )
    await db["log_extraction_prompts"].update_one(
        {"_id": "default"},
        {"$setOnInsert": {
            "_id": "default",
            "model": "default",
            "is_default": True,
            "system_prompt": LOG_EXTRACTION_SYSTEM_PROMPT,
            "user_template": LOG_EXTRACTION_USER_PROMPT_TPL,
            "updated_by": "system",
            "updated_at": utc_now_iso(),
        }},
        upsert=True
    )

"""
MongoDB 索引初始化 - 应用启动时自动创建必要的索引
"""
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


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
        [("status", 1), ("started_at", -1)], name="idx_sync_jobs_status_started"
    )
    await db["sync_jobs"].create_index("started_at", name="idx_sync_jobs_started_at")

    # ---- sync_remote_servers ----
    await db["sync_remote_servers"].create_index(
        "server_sn", unique=True, name="idx_sync_servers_sn"
    )
    await db["sync_remote_servers"].create_index("synced_at", name="idx_sync_servers_synced_at")

    # ---- sync_remote_test_details ----
    await db["sync_remote_test_details"].create_index(
        [("server_id", 1), ("detailed_flow", 1), ("test_time", 1)],
        name="idx_sync_details_server_flow_time"
    )
    await db["sync_remote_test_details"].create_index(
        [("server_sn", 1), ("test_time", -1)], name="idx_sync_details_sn_time"
    )

    # ---- analytics 聚合索引 ----
    # 配合时间范围 $match（test_time: {$gte: ...}）快速过滤
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

    logger.info("MongoDB indexes ensured successfully")

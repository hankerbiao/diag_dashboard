"""
MongoDB 索引初始化脚本

运行方式:
    cd diag_backend
    source .venv/bin/activate
    python -m migrations.init_mongodb
"""
import asyncio
from pymongo import ASCENDING, DESCENDING

from app.core.config import get_settings
from app.core.mongodb import connect_mongodb, close_mongodb, get_database


async def create_indexes():
    """创建所有必要的索引"""
    settings = get_settings()
    print(f"Connecting to MongoDB: {settings.mongodb_uri}/{settings.mongodb_db_name}")

    await connect_mongodb()
    db = get_database()

    # ===== users =====
    await db.users.create_index(
        "itcode", unique=True, sparse=True, name="idx_users_itcode"
    )
    print("  ✓ users.itcode (unique, sparse)")

    # ===== sync_jobs =====
    await db.sync_jobs.create_index("status")
    await db.sync_jobs.create_index([("started_at", DESCENDING)])
    print("  ✓ sync_jobs (status, started_at)")

    # ===== sync_remote_servers =====
    await db.sync_remote_servers.create_index("server_sn", unique=True)
    await db.sync_remote_servers.create_index([("synced_at", DESCENDING)])
    await db.sync_remote_servers.create_index("model")
    await db.sync_remote_servers.create_index("customer_id")
    print("  ✓ sync_remote_servers (server_sn unique, synced_at, model, customer_id)")

    # ===== sync_remote_test_details =====
    await db.sync_remote_test_details.create_index([
        ("server_id", ASCENDING),
        ("detailed_flow", ASCENDING),
        ("test_time", ASCENDING)
    ], unique=True)
    await db.sync_remote_test_details.create_index("server_sn")
    await db.sync_remote_test_details.create_index([("test_time", DESCENDING)])
    print("  ✓ sync_remote_test_details (compound unique, server_sn, test_time)")

    # ===== app_settings =====
    await db.app_settings.create_index("user_id", unique=True)
    print("  ✓ app_settings.user_id (unique)")

    # ===== case_library =====
    await db.case_library.create_index("error_code")
    await db.case_library.create_index([("root_cause", "text")])  # 文本搜索索引
    print("  ✓ case_library (error_code, root_cause text)")

    # ===== devices =====
    await db.devices.create_index("sn", unique=True)
    await db.devices.create_index("model")
    print("  ✓ devices (sn unique, model)")

    # ===== error_logs =====
    await db.error_logs.create_index("device_id")
    await db.error_logs.create_index([("test_time", DESCENDING)])
    await db.error_logs.create_index("factory")
    print("  ✓ error_logs (device_id, test_time, factory)")

    # ===== factories =====
    await db.factories.create_index("name")
    print("  ✓ factories (name)")

    # ===== maintenance_records =====
    await db.maintenance_records.create_index("device_id")
    await db.maintenance_records.create_index([("date", DESCENDING)])
    print("  ✓ maintenance_records (device_id, date)")

    await close_mongodb()
    print("\nAll indexes created successfully!")


async def drop_all_indexes():
    """删除所有索引（谨慎使用）"""
    settings = get_settings()
    print(f"Connecting to MongoDB: {settings.mongodb_uri}/{settings.mongodb_db_name}")

    await connect_mongodb()
    db = get_database()

    collections = [
        "users", "sync_jobs", "sync_remote_servers", "sync_remote_test_details",
        "app_settings", "case_library", "devices", "error_logs",
        "factories", "maintenance_records"
    ]

    for col_name in collections:
        await db[col_name].drop_indexes()
        print(f"  ✓ {col_name} indexes dropped")

    await close_mongodb()
    print("\nAll indexes dropped!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        print("WARNING: This will delete all indexes!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            asyncio.run(drop_all_indexes())
        else:
            print("Cancelled.")
    else:
        asyncio.run(create_indexes())

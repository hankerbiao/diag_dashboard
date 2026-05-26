"""
MongoDB 连接管理模块
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional

from .config import get_settings

_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None


async def connect_mongodb():
    """建立 MongoDB 连接"""
    global _client, _database
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _database = _client[settings.mongodb_db_name]
    # 验证连接
    await _client.admin.command("ping")
    # 自动创建索引和种子数据
    from .mongodb_indexes import ensure_indexes, seed_default_data
    await ensure_indexes(_database)
    await seed_default_data(_database)
    print(f"Connected to MongoDB: {settings.mongodb_uri}/{settings.mongodb_db_name}")


async def close_mongodb():
    """关闭 MongoDB 连接"""
    global _client, _database
    if _client:
        _client.close()
        _client = None
        _database = None
        print("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """获取数据库实例"""
    if _database is None:
        raise RuntimeError("MongoDB not connected. Call connect_mongodb() first.")
    return _database


def get_collection(name: str):
    """获取集合"""
    return get_database()[name]
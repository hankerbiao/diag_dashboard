"""
数据同步服务 - 查询已同步到 MongoDB 的服务器及测试数据
数据写入由独立脚本 (scripts/sync_data.py) 完成
"""
import logging
from typing import Optional

from ..core.mongodb import get_collection

logger = logging.getLogger(__name__)


class SyncService:
    """数据查询服务（只读）"""

    # ════════════════════════════════════════════════════
    # 数据查询
    # ════════════════════════════════════════════════════

    async def get_jobs(self, factory_id: Optional[str] = None, page: int = 1, limit: int = 5) -> dict:
        col = get_collection("sync_jobs")
        query = {}
        if factory_id:
            query["factory_id"] = factory_id
        total = await col.count_documents(query)
        skip = (page - 1) * limit
        cursor = col.find(query).sort("started_at", -1).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)
        for item in items:
            item["id"] = str(item.pop("_id"))
        return {"items": items, "total": total, "page": page, "limit": limit}

    async def get_servers(
        self,
        factory_id: Optional[str] = None,
        search_sn: Optional[str] = None,
        search_product_models: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        col = get_collection("sync_remote_servers")
        query = {}
        if factory_id:
            query["factory_id"] = factory_id
        if search_sn:
            query["server_sn"] = {"$regex": search_sn, "$options": "i"}
        if search_product_models:
            query["product_models"] = {"$regex": search_product_models, "$options": "i"}

        total = await col.count_documents(query)
        skip = (page - 1) * limit
        cursor = col.find(query).sort("synced_at", -1).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)

        for item in items:
            item["id"] = str(item.pop("_id"))

        return {"items": items, "total": total, "page": page, "limit": limit}

    async def get_test_details(self, server_sn: str, factory_id: Optional[str] = None, page: int = 1, limit: int = 20) -> dict:
        col = get_collection("sync_remote_test_details")
        query = {"server_sn": server_sn}
        if factory_id:
            query["factory_id"] = factory_id
        total = await col.count_documents(query)
        skip = (page - 1) * limit
        cursor = col.find(query).sort("test_time", -1).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)

        for item in items:
            item["id"] = str(item.pop("_id"))

        return {"items": items, "total": total, "page": page, "limit": limit}


_sync_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service

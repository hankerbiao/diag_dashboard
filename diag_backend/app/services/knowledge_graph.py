"""
知识图谱检索服务
"""
import logging
from typing import Optional

from bson import ObjectId

from ..core.mongodb import get_collection

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """知识图谱检索服务"""

    def __init__(self):
        pass

    async def find_similar_cases(
        self,
        error_description: str,
        error_code: Optional[str] = None,
        limit: int = 5
    ) -> list[dict]:
        """查找相似案例"""
        col = get_collection("case_library")
        query = {}

        if error_code:
            query["error_code"] = error_code

        # 模糊匹配 root_cause
        if error_description and error_description.strip():
            query["$text"] = {"$search": error_description.strip()}

        if not query:
            return []

        cursor = col.find(query).limit(limit)
        cases = await cursor.to_list(length=limit)

        if not cases:
            return []

        # 转换 ObjectId
        for case in cases:
            case["id"] = str(case.pop("_id"))
        return cases

    async def get_device_test_logs(
        self,
        device_id: str,
        limit: int = 20
    ) -> list[dict]:
        """获取设备测试日志"""
        try:
            oid = ObjectId(device_id)
        except Exception:
            return []

        # 先获取设备信息
        devices_col = get_collection("devices")
        device = await devices_col.find_one({"_id": oid})
        if not device:
            return []

        # 查询 error_logs
        logs_col = get_collection("error_logs")
        cursor = logs_col.find({"device_id": device_id}).sort("test_time", -1).limit(limit)
        logs = await cursor.to_list(length=limit)

        for log in logs:
            log["id"] = str(log.pop("_id"))
            log["device_sn"] = device.get("sn")
            log["device_model"] = device.get("model")

        return logs

    async def get_device_maintenance_history(
        self,
        device_id: str,
        limit: int = 10
    ) -> list[dict]:
        """获取设备维修历史"""
        try:
            ObjectId(device_id)
        except Exception:
            return []

        col = get_collection("maintenance_records")
        cursor = col.find({"device_id": device_id}).sort("date", -1).limit(limit)
        records = await cursor.to_list(length=limit)

        for record in records:
            record["id"] = str(record.pop("_id"))
        return records

    async def get_device_by_sn(self, sn: str) -> Optional[dict]:
        """通过 SN 获取设备信息"""
        col = get_collection("devices")
        device = await col.find_one({"sn": sn})
        if device:
            device["id"] = str(device.pop("_id"))
        return device

    async def get_error_log_by_id(self, error_log_id: str) -> Optional[dict]:
        """通过 ID 获取异常日志详情"""
        try:
            oid = ObjectId(error_log_id)
        except Exception:
            return None
        try:
            col = get_collection("error_logs")
            log = await col.find_one({"_id": oid})
            if log:
                log["id"] = str(log.pop("_id"))
            return log
        except Exception as e:
            logger.error("Failed to fetch error log %s: %s", error_log_id, e)
            return None


# 全局实例
knowledge_graph = KnowledgeGraphService()
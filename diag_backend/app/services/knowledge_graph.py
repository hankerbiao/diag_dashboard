"""
知识图谱检索服务
"""
from typing import Optional

from ..core.mongodb import get_collection


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
        if error_description:
            query["root_cause"] = {"$regex": error_description[:20], "$options": "i"}

        cursor = col.find(query).limit(limit)
        cases = await cursor.to_list(length=limit)

        if not cases:
            return self._mock_cases()

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
        # 先获取设备信息
        devices_col = get_collection("devices")
        device = await devices_col.find_one({"_id": device_id})
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

        # Mock data for development
        return {
            "id": "mock-device-id",
            "sn": sn,
            "model": "2U Rack Server",
            "batch": "#8821",
            "factory": {"name": "天津"}
        }

    def _mock_cases(self) -> list[dict]:
        """开发环境模拟数据"""
        return [
            {
                "id": "case-1",
                "title": "DIMM 奇偶校验失败案例",
                "error_code": "0x822",
                "root_cause": "DIMM插槽4电压离散跳动",
                "repair_steps": [
                    "执行 ECC 寄存器清除",
                    "更换增强型 DDR4 内存",
                    "重刷电压阈值固件"
                ]
            },
            {
                "id": "case-2",
                "title": "批次 #8821 高温失效",
                "error_code": "0x823",
                "root_cause": "批次料件高温负荷不耐受",
                "repair_steps": [
                    "替换为新批次料件",
                    "降频运行验证"
                ]
            }
        ]


# 全局实例
knowledge_graph = KnowledgeGraphService()
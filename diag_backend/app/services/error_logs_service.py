"""
Error Logs Service - 从 sync_remote_test_details 聚合异常日志统计
替代原有的 Mock 数据
"""
import logging
from datetime import timedelta
from ..core.utils import utc_now
from typing import Optional

from ..core.mongodb import get_collection

logger = logging.getLogger(__name__)

DETAILS_COLLECTION = "sync_remote_test_details"


class ErrorLogsService:

    async def get_stats(
        self,
        factory: str,
        time_range: str = "day",
    ) -> dict:
        """获取异常统计数据（趋势、直通率、问题类型、线体分布）"""
        days = {"day": 7, "week": 28, "month": 90}.get(time_range, 7)
        since = (utc_now() - timedelta(days=days)).isoformat()

        match_filter: dict = {"test_time": {"$gte": since}}
        if factory:
            match_filter["factory_id"] = factory

        col = get_collection(DETAILS_COLLECTION)

        trend, yield_trend, by_type, by_line = await self._aggregate_all(
            col, match_filter, time_range, days
        )

        return {
            "trend": trend,
            "yield_trend": yield_trend,
            "by_type": by_type,
            "by_line": by_line,
        }

    async def get_trend(
        self,
        factory: str,
        time_range: str = "day",
    ) -> list[dict]:
        """获取阻断历史趋势"""
        days = {"day": 7, "week": 28, "month": 90}.get(time_range, 7)
        since = (utc_now() - timedelta(days=days)).isoformat()

        match_filter: dict = {"test_time": {"$gte": since}}
        if factory:
            match_filter["factory_id"] = factory

        col = get_collection(DETAILS_COLLECTION)
        return await self._agg_trend(col, match_filter, time_range)

    async def get_yield_trend(
        self,
        factory: str,
    ) -> list[dict]:
        """获取直通率趋势（近 7 天）"""
        since = (utc_now() - timedelta(days=7)).isoformat()

        match_filter: dict = {"test_time": {"$gte": since}}
        if factory:
            match_filter["factory_id"] = factory

        col = get_collection(DETAILS_COLLECTION)
        return await self._agg_yield(col, match_filter)

    async def _aggregate_all(self, col, match_filter: dict, time_range: str, days: int):
        import asyncio

        results = await asyncio.gather(
            self._agg_trend(col, match_filter, time_range),
            self._agg_yield(col, match_filter),
            self._agg_by_type(col, match_filter),
            self._agg_by_line(col, match_filter),
        )
        return results[0], results[1], results[2], results[3]

    async def _agg_trend(self, col, match_filter: dict, time_range: str) -> list[dict]:
        """按时间聚合问题数量"""
        n = 7 if time_range == "month" else 10
        pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": {"$substr": ["$test_time", 0, n]},
                "issues": {"$sum": 1},
            }},
            {"$sort": {"_id": 1}},
            {"$project": {"time": "$_id", "issues": 1, "_id": 0}},
        ]
        return await self._run(col, pipeline)

    async def _agg_yield(self, col, match_filter: dict) -> list[dict]:
        """按日期聚合直通率"""
        pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": {"$substr": ["$test_time", 0, 10]},
                "total": {"$sum": 1},
                "passed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "成功"]}, 1, 0]}},
                "failed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "失败"]}, 1, 0]}},
            }},
            {"$sort": {"_id": 1}},
            {"$project": {
                "date": "$_id",
                "total": 1,
                "passed": 1,
                "failed": 1,
                "yield": {
                    "$cond": [
                        {"$gt": ["$total", 0]},
                        {"$round": [{"$multiply": [{"$divide": ["$passed", "$total"]}, 100]}, 1]},
                        0,
                    ]
                },
                "_id": 0,
            }},
        ]
        return await self._run(col, pipeline)

    async def _agg_by_type(self, col, match_filter: dict) -> list[dict]:
        """按故障主类别聚合"""
        pipeline = [
            {"$match": {**match_filter, "fault_type1": {"$ne": ""}}},
            {"$group": {"_id": "$fault_type1", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
            {"$project": {"name": "$_id", "count": 1, "_id": 0}},
        ]
        return await self._run(col, pipeline)

    async def _agg_by_line(self, col, match_filter: dict) -> list[dict]:
        """按工站（线体）聚合"""
        pipeline = [
            {"$match": {**match_filter, "detailed_flow": {"$ne": ""}}},
            {"$group": {"_id": "$detailed_flow", "issues": {"$sum": 1}}},
            {"$sort": {"issues": -1}},
            {"$limit": 10},
            {"$project": {"line": "$_id", "issues": 1, "_id": 0}},
        ]
        return await self._run(col, pipeline)

    @staticmethod
    async def _run(col, pipeline: list[dict]) -> list[dict]:
        try:
            cursor = col.aggregate(pipeline, allowDiskUse=True)
            return await cursor.to_list(length=1000)
        except Exception as e:
            logger.error(f"ErrorLogs aggregation failed: {e}", exc_info=True)
            return []


_error_logs_service: Optional[ErrorLogsService] = None


def get_error_logs_service() -> ErrorLogsService:
    global _error_logs_service
    if _error_logs_service is None:
        _error_logs_service = ErrorLogsService()
    return _error_logs_service

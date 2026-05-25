"""
Analytics Service - MongoDB 聚合管道提供看板图表数据（带内存缓存）
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..core.mongodb import get_collection

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 缓存 5 分钟


def _cache_key(search_sn: str, search_product_models: str, days: int, trend: str) -> str:
    return f"insights:{search_sn or ''}:{search_product_models or ''}:{days}:{trend}"


class AnalyticsService:

    def __init__(self):
        self._cache: dict[str, tuple[float, dict]] = {}

    async def get_dashboard_insights(
        self,
        search_sn: Optional[str] = None,
        search_product_models: Optional[str] = None,
        days: int = 30,
        trend: str = "day",
    ) -> dict:
        ck = _cache_key(search_sn or "", search_product_models or "", days, trend)
        now = time.monotonic()
        if ck in self._cache:
            ts, data = self._cache[ck]
            if now - ts < CACHE_TTL:
                return data

        details_col = get_collection("sync_remote_test_details")
        servers_col = get_collection("sync_remote_servers")

        # 构建基础过滤条件
        match_filter: dict = {}

        # 按 SN 过滤
        server_ids: list[str] = []
        if search_sn:
            sn_filter = {"server_sn": {"$regex": search_sn, "$options": "i"}}
            cursor = servers_col.find(sn_filter, {"_id": 1})
            async for doc in cursor:
                server_ids.append(str(doc["_id"]))
            if not server_ids:
                return self._empty_insights()
            match_filter["server_id"] = {"$in": server_ids}

        # 按产品型号过滤
        if search_product_models:
            pm_filter = {"product_models": {"$regex": search_product_models, "$options": "i"}}
            sn_from_pm = []
            cursor = servers_col.find(pm_filter, {"_id": 1})
            async for doc in cursor:
                sn_from_pm.append(str(doc["_id"]))
            if not sn_from_pm:
                return self._empty_insights()
            if "server_id" in match_filter:
                existing = set(match_filter["server_id"]["$in"])
                pm_set = set(sn_from_pm)
                match_filter["server_id"]["$in"] = list(existing & pm_set)
                if not match_filter["server_id"]["$in"]:
                    return self._empty_insights()
            else:
                match_filter["server_id"] = {"$in": sn_from_pm}

        # 时间范围
        since = datetime.now(timezone.utc) - timedelta(days=days)
        time_filter = {"test_time": {"$gte": since.isoformat()}}
        if match_filter:
            match_filter = {"$and": [match_filter, time_filter]}
        else:
            match_filter = time_filter

        # 并行执行 6 个聚合管道
        results = await asyncio.gather(
            self._agg_fault_categories(details_col, match_filter),
            self._agg_fault_subcategories(details_col, match_filter),
            self._agg_yield_trend(details_col, match_filter, trend),
            self._agg_station_failures(details_col, match_filter),
            self._agg_decision_distribution(details_col, match_filter),
            self._agg_model_defects(details_col, servers_col, match_filter),
        )

        data = {
            "fault_categories": results[0],
            "fault_subcategories": results[1],
            "yield_trend": results[2],
            "station_failures": results[3],
            "decision_distribution": results[4],
            "model_defects": results[5],
        }
        self._cache[ck] = (now, data)
        return data

    def _empty_insights(self) -> dict:
        return {
            "fault_categories": [],
            "fault_subcategories": [],
            "yield_trend": [],
            "station_failures": [],
            "decision_distribution": [],
            "model_defects": [],
        }

    # ── Chart 1: 故障主类别分布 ──

    async def _agg_fault_categories(self, col, match_filter: dict) -> list[dict]:
        pipeline = [
            {"$match": {**match_filter, "fault_type1": {"$ne": ""}}},
            {"$group": {"_id": "$fault_type1", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
            {"$project": {"name": "$_id", "count": 1, "_id": 0}},
        ]
        return await self._run_pipeline(col, pipeline)

    # ── Chart 2: 故障子类别 TOP10 ──

    async def _agg_fault_subcategories(self, col, match_filter: dict) -> list[dict]:
        pipeline = [
            {"$match": {**match_filter, "fault_type2": {"$ne": ""}}},
            {"$group": {"_id": "$fault_type2", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
            {"$project": {"name": "$_id", "count": 1, "_id": 0}},
        ]
        return await self._run_pipeline(col, pipeline)

    # ── Chart 3: 良率趋势（支持日/周/月切换） ──

    async def _agg_yield_trend(self, col, match_filter: dict, trend: str = "day") -> list[dict]:
        if trend == "month":
            group_id = {"$substr": ["$test_time", 0, 7]}
            pipeline = [
                {"$match": match_filter},
                {"$group": {
                    "_id": group_id,
                    "total": {"$sum": 1},
                    "passed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "成功"]}, 1, 0]}},
                    "failed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "失败"]}, 1, 0]}},
                }},
                {"$sort": {"_id": 1}},
                {"$project": {
                    "date": "$_id", "total": 1, "passed": 1, "failed": 1,
                    "yield": {"$cond": [{"$gt": ["$total", 0]}, {"$round": [{"$multiply": [{"$divide": ["$passed", "$total"]}, 100]}, 1]}, 0]},
                    "_id": 0,
                }},
            ]
        elif trend == "week":
            pipeline = [
                {"$match": match_filter},
                {"$group": {
                    "_id": {
                        "year": {"$isoWeekYear": {"$dateFromString": {"dateString": "$test_time"}}},
                        "week": {"$isoWeek": {"$dateFromString": {"dateString": "$test_time"}}},
                    },
                    "total": {"$sum": 1},
                    "passed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "成功"]}, 1, 0]}},
                    "failed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "失败"]}, 1, 0]}},
                }},
                {"$sort": {"_id.year": 1, "_id.week": 1}},
                {"$project": {
                    "date": {"$concat": [
                        {"$toString": "$_id.year"}, "-W",
                        {"$cond": [{"$lt": ["$_id.week", 10]}, {"$concat": ["0", {"$toString": "$_id.week"}]}, {"$toString": "$_id.week"}]},
                    ]},
                    "total": 1, "passed": 1, "failed": 1,
                    "yield": {"$cond": [{"$gt": ["$total", 0]}, {"$round": [{"$multiply": [{"$divide": ["$passed", "$total"]}, 100]}, 1]}, 0]},
                    "_id": 0,
                }},
            ]
        else:
            group_id = {"$substr": ["$test_time", 0, 10]}
            pipeline = [
                {"$match": match_filter},
                {"$group": {
                    "_id": group_id,
                    "total": {"$sum": 1},
                    "passed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "成功"]}, 1, 0]}},
                    "failed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "失败"]}, 1, 0]}},
                }},
                {"$sort": {"_id": 1}},
                {"$project": {
                    "date": "$_id", "total": 1, "passed": 1, "failed": 1,
                    "yield": {"$cond": [{"$gt": ["$total", 0]}, {"$round": [{"$multiply": [{"$divide": ["$passed", "$total"]}, 100]}, 1]}, 0]},
                    "_id": 0,
                }},
            ]

        return await self._run_pipeline(col, pipeline)

    # ── Chart 4: 工站失败数 TOP10 ──

    async def _agg_station_failures(self, col, match_filter: dict) -> list[dict]:
        pipeline = [
            {"$match": {**match_filter, "server_test_result": {"$ne": "成功"}, "detailed_flow": {"$ne": ""}}},
            {"$group": {"_id": "$detailed_flow", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
            {"$project": {"station": "$_id", "count": 1, "_id": 0}},
        ]
        return await self._run_pipeline(col, pipeline)

    # ── Chart 5: 判定结果分布 ──

    async def _agg_decision_distribution(self, col, match_filter: dict) -> list[dict]:
        pipeline = [
            {"$match": {**match_filter, "decision": {"$ne": ""}}},
            {"$group": {"_id": "$decision", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$project": {"decision": "$_id", "count": 1, "_id": 0}},
        ]
        return await self._run_pipeline(col, pipeline)

    # ── Chart 6: 机型测试数据对比
    # 优化：先 $match 过滤时间范围，再 $lookup，大幅减少扫描量

    async def _agg_model_defects(self, details_col, servers_col, match_filter: dict) -> list[dict]:
        pipeline = [
            {"$match": match_filter},
            {"$lookup": {
                "from": "sync_remote_servers",
                "localField": "server_sn",
                "foreignField": "server_sn",
                "as": "server_info",
            }},
            {"$unwind": "$server_info"},
            {"$match": {"server_info.product_models": {"$ne": ""}}},
            {"$group": {
                "_id": "$server_info.product_models",
                "total": {"$sum": 1},
                "failed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "失败"]}, 1, 0]}},
                "latest_test": {"$max": "$test_time"},
            }},
            {"$sort": {"latest_test": -1}},
            {"$limit": 10},
            {"$project": {
                "model": "$_id",
                "total": 1,
                "failed": 1,
                "yield": {
                    "$cond": [
                        {"$gt": ["$total", 0]},
                        {"$round": [{"$multiply": [{"$divide": [{"$subtract": ["$total", "$failed"]}, "$total"]}, 100]}, 1]},
                        0,
                    ]
                },
                "_id": 0,
            }},
        ]
        return await self._run_pipeline(details_col, pipeline)

    @staticmethod
    async def _run_pipeline(col, pipeline: list[dict]) -> list[dict]:
        try:
            cursor = col.aggregate(pipeline, allowDiskUse=True)
            return await cursor.to_list(length=1000)
        except Exception as e:
            logger.error(f"Aggregation pipeline failed: {e}", exc_info=True)
            return []


_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service

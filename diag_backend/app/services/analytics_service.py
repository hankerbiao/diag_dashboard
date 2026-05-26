"""
Analytics Service - 每小时后台预计算看板数据并持久化到 MongoDB
前端直接读取预计算结果，不再触发实时聚合
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..core.factory_config import load_factories_from_yaml
from ..core.mongodb import get_collection

logger = logging.getLogger(__name__)

SNAPSHOT_COLLECTION = "analytics_snapshots"
DEFAULT_SNAPSHOT_DAYS = 30


def _cache_key(trend: str, days: int, factory_id: Optional[str] = None,
               search_sn: Optional[str] = None, search_product_models: Optional[str] = None) -> str:
    parts = [f"insights:{trend}:{days}"]
    if factory_id:
        parts.append(f"fac:{factory_id}")
    if search_sn:
        parts.append(f"sn:{search_sn}")
    if search_product_models:
        parts.append(f"pm:{search_product_models}")
    return ":".join(parts)


class AnalyticsService:

    def __init__(self):
        self._scheduler_task: Optional[asyncio.Task] = None
        self._scheduler_stop = asyncio.Event()

    # ════════════════════════════════════════════════════
    # 公开方法
    # ════════════════════════════════════════════════════

    async def get_dashboard_insights(
        self,
        factory_id: Optional[str] = None,
        search_sn: Optional[str] = None,
        search_product_models: Optional[str] = None,
        days: int = 30,
        trend: str = "day",
    ) -> dict:
        ck = _cache_key(trend, days, factory_id, search_sn, search_product_models)

        # 带过滤条件（SN/产品型号）的请求 → 实时计算（无法预计算所有组合）
        if search_sn or search_product_models:
            return await self._compute(days, trend, factory_id, search_sn, search_product_models)

        # 预计算快照读取
        snapshot = await self._get_snapshot(ck)
        if snapshot:
            return snapshot["data"]

        # 首次启动尚无快照 → 实时计算并保存
        logger.info("Snapshot not found, computing on-demand: %s", ck)
        data = await self._compute(days, trend, factory_id)
        await self._save_snapshot(ck, data)
        return data

    async def refresh_all_snapshots(self) -> None:
        """刷新所有预计算快照（全量趋势 × 厂区组合）"""
        logger.info("Refreshing all analytics snapshots...")

        sem = asyncio.Semaphore(5)

        async def bounded_compute(trend, days, factory_id=None):
            async with sem:
                await self._compute_and_save(trend, days, factory_id)

        tasks = []
        # 总览（无厂区过滤）
        for trend in ("day", "week", "month"):
            tasks.append(bounded_compute(trend, DEFAULT_SNAPSHOT_DAYS))

        # 各厂区（从 YAML 配置读取）
        factories = load_factories_from_yaml()
        for factory in factories:
            fid = factory["factory_id"]
            for trend in ("day", "week", "month"):
                tasks.append(bounded_compute(trend, DEFAULT_SNAPSHOT_DAYS, factory_id=fid))

        await asyncio.gather(*tasks)
        logger.info("All analytics snapshots refreshed")

    async def _compute_and_save(self, trend: str, days: int = 30, factory_id: Optional[str] = None):
        """计算单个快照并持久化"""
        try:
            data = await self._compute(days, trend, factory_id)
            ck = _cache_key(trend, days, factory_id)
            await self._save_snapshot(ck, data)
        except Exception as e:
            logger.error("Snapshot compute failed for %s trend=%s fac=%s: %s", trend, days, factory_id, e)

    # ════════════════════════════════════════════════════
    # 快照持久化 (MongoDB)
    # ════════════════════════════════════════════════════

    async def _get_snapshot(self, key: str) -> Optional[dict]:
        try:
            col = get_collection(SNAPSHOT_COLLECTION)
            return await col.find_one({"_id": key})
        except Exception as e:
            logger.warning("Snapshot read failed: %s", e)
            return None

    async def _save_snapshot(self, key: str, data: dict) -> None:
        try:
            col = get_collection(SNAPSHOT_COLLECTION)
            await col.update_one(
                {"_id": key},
                {"$set": {
                    "data": data,
                    "computed_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
        except Exception as e:
            logger.warning("Snapshot write failed: %s", e)

    # ════════════════════════════════════════════════════
    # 聚合计算（与之前保持一致）
    # ════════════════════════════════════════════════════

    async def _compute(self, days: int, trend: str,
                       factory_id: Optional[str] = None,
                       search_sn: Optional[str] = None,
                       search_product_models: Optional[str] = None) -> dict:
        details_col = get_collection("sync_remote_test_details")
        servers_col = get_collection("sync_remote_servers")

        since = datetime.now(timezone.utc) - timedelta(days=days)
        match_filter: dict = {"test_time": {"$gte": since.isoformat()}}

        if factory_id:
            match_filter["factory_id"] = factory_id

        if search_sn:
            match_filter["server_sn"] = {"$regex": search_sn, "$options": "i"}

        if search_product_models:
            cursor = servers_col.find(
                {"product_models": {"$regex": search_product_models, "$options": "i"}},
                {"server_sn": 1}
            )
            sns = [doc["server_sn"] async for doc in cursor]
            if not sns:
                return self._empty_insights()
            match_filter["server_sn"] = {"$in": sns}

        results = await asyncio.gather(
            self._agg_fault_categories(details_col, match_filter),
            self._agg_fault_subcategories(details_col, match_filter),
            self._agg_yield_trend(details_col, match_filter, trend),
            self._agg_station_failures(details_col, match_filter),
            self._agg_decision_distribution(details_col, match_filter),
            self._agg_model_defects(details_col, servers_col, match_filter),
        )

        return {
            "fault_categories": results[0],
            "fault_subcategories": results[1],
            "yield_trend": results[2],
            "station_failures": results[3],
            "decision_distribution": results[4],
            "model_defects": results[5],
        }

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

    # ── Chart 3: 良率趋势（日/周/月） ──

    @staticmethod
    def _yield_project(date_expr: dict) -> dict:
        return {
            "date": date_expr, "total": 1, "passed": 1, "failed": 1,
            "yield": {"$cond": [{"$gt": ["$total", 0]},
                                {"$round": [{"$multiply": [{"$divide": ["$passed", "$total"]}, 100]}, 1]}, 0]},
            "_id": 0,
        }

    async def _agg_yield_trend(self, col, match_filter: dict, trend: str) -> list[dict]:
        if trend == "week":
            group_id = {
                "year": {"$isoWeekYear": {"$dateFromString": {"dateString": "$test_time"}}},
                "week": {"$isoWeek": {"$dateFromString": {"dateString": "$test_time"}}},
            }
            pipeline = [
                {"$match": match_filter},
                {"$group": {"_id": group_id, "total": {"$sum": 1},
                            "passed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "成功"]}, 1, 0]}},
                            "failed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "失败"]}, 1, 0]}}}},
                {"$sort": {"_id.year": 1, "_id.week": 1}},
                {"$project": self._yield_project({
                    "$concat": [
                        {"$toString": "$_id.year"}, "-W",
                        {"$cond": [{"$lt": ["$_id.week", 10]}, {"$concat": ["0", {"$toString": "$_id.week"}]}, {"$toString": "$_id.week"}]},
                    ]
                })},
            ]
        else:
            n = 7 if trend == "month" else 10
            pipeline = [
                {"$match": match_filter},
                {"$group": {"_id": {"$substr": ["$test_time", 0, n]}, "total": {"$sum": 1},
                            "passed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "成功"]}, 1, 0]}},
                            "failed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "失败"]}, 1, 0]}}}},
                {"$sort": {"_id": 1}},
                {"$project": self._yield_project("$_id")},
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

    # ── Chart 6: 机型测试数据对比 ──

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

    # ════════════════════════════════════════════════════
    # 调度器
    # ════════════════════════════════════════════════════

    async def _scheduler_loop(self):
        """每小时执行一次全量快照刷新"""
        logger.info("Analytics snapshot scheduler started")

        # 启动后立即执行一次
        await self.refresh_all_snapshots()

        try:
            while not self._scheduler_stop.is_set():
                try:
                    await asyncio.wait_for(
                        self._scheduler_stop.wait(),
                        timeout=3600.0
                    )
                except asyncio.TimeoutError:
                    pass
                except asyncio.CancelledError:
                    break

                if self._scheduler_stop.is_set():
                    break

                await self.refresh_all_snapshots()
        finally:
            logger.info("Analytics snapshot scheduler stopped")

    def start_scheduler(self):
        """启动后台调度器"""
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_stop.clear()
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            logger.info("Analytics scheduler started")

    @property
    def is_scheduler_running(self) -> bool:
        return self._scheduler_task is not None and not self._scheduler_task.done()

    async def stop_scheduler(self):
        """停止后台调度器"""
        self._scheduler_stop.set()
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None
            logger.info("Analytics scheduler stopped")


_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service

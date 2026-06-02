"""Analytics Service - Pre-computed dashboard data cached in MongoDB"""
import asyncio
import logging
from datetime import timedelta
from ..core.utils import utc_now
from typing import Optional
from pymongo.errors import OperationFailure
from ..core.factory_config import load_factories_from_yaml
from ..core.mongodb import get_collection

SNAPSHOT_COLLECTION = "analytics_snapshots"
DEFAULT_DAYS = 30


def _key(trend: str, days: int, **kwargs) -> str:
    return ":".join([f"insights:{trend}:{days}"] + [f"{k[:2]}:{v}" for k, v in kwargs.items() if v])


class AnalyticsService:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    async def get_insights(self, factory_id: Optional[str] = None, search_sn: Optional[str] = None,
                           search_product_models: Optional[str] = None, days: int = 30, trend: str = "day") -> dict:
        ck = _key(trend, days, fac=factory_id, sn=search_sn, pm=search_product_models)
        if search_sn or search_product_models:
            return await self._compute(days, trend, factory_id, search_sn, search_product_models)
        snapshot = await self._get(ck)
        if snapshot:
            return snapshot["data"]
        data = await self._compute(days, trend, factory_id)
        await self._save(ck, data)
        return data

    async def refresh_all(self) -> None:
        sem = asyncio.Semaphore(5)

        async def bounded(t: str, d: int, f: Optional[str] = None):
            async with sem:
                await self._compute_and_save(t, d, f)

        tasks = [bounded(t, DEFAULT_DAYS) for t in ("day", "week", "month")]
        tasks += [bounded(t, DEFAULT_DAYS, f["factory_id"]) for f in load_factories_from_yaml() for t in ("day", "week", "month")]
        await asyncio.gather(*tasks)

    async def _compute_and_save(self, trend: str, days: int, factory_id: Optional[str] = None):
        try:
            data = await self._compute(days, trend, factory_id)
            await self._save(_key(trend, days, fac=factory_id), data)
        except Exception as e:
            logging.error("Snapshot failed trend=%s fac=%s: %s", trend, factory_id, e)

    async def _get(self, key: str) -> Optional[dict]:
        try:
            return await get_collection(SNAPSHOT_COLLECTION).find_one({"_id": key})
        except Exception:
            return None

    async def _save(self, key: str, data: dict) -> None:
        try:
            await get_collection(SNAPSHOT_COLLECTION).update_one(
                {"_id": key},
                {"$set": {"data": data, "computed_at": utc_now()}},
                upsert=True)
        except Exception:
            pass

    async def _compute(self, days: int, trend: str, factory_id: Optional[str] = None,
                       search_sn: Optional[str] = None, search_product_models: Optional[str] = None) -> dict:
        details = get_collection("sync_remote_test_details")
        servers = get_collection("sync_remote_servers")
        match = {"test_time": {"$gte": (utc_now() - timedelta(days=days)).isoformat()}}
        if factory_id:
            match["factory_id"] = factory_id
        if search_sn:
            match["server_sn"] = {"$regex": search_sn, "$options": "i"}
        if search_product_models:
            sns = [d["server_sn"] async for d in servers.find(
                {"product_models": {"$regex": search_product_models, "$options": "i"}}, {"server_sn": 1})]
            if not sns:
                return self._empty()
            match["server_sn"] = {"$in": sns}

        results = await asyncio.gather(
            self._agg(details, {**match, "fault_type1": {"$ne": ""}}, "$fault_type1", "name", limit=10),
            self._agg(details, {**match, "fault_type2": {"$ne": ""}}, "$fault_type2", "name", limit=10),
            self._yield_trend(details, match, trend),
            self._agg(details, {**match, "server_test_result": {"$ne": "成功"}, "detailed_flow": {"$ne": ""}}, "$detailed_flow", "station", limit=10),
            self._agg(details, {**match, "decision": {"$ne": ""}}, "$decision", "decision", limit=100),
            self._model_defects(details, servers, match),
        )
        return dict(zip(["fault_categories", "fault_subcategories", "yield_trend", "station_failures",
                         "decision_distribution", "model_defects"], results))

    def _empty(self) -> dict:
        return {k: [] for k in ["fault_categories", "fault_subcategories", "yield_trend",
                                "station_failures", "decision_distribution", "model_defects"]}

    async def _agg(self, col, match: dict, group_id: str, project_field: str, limit: int = 10) -> list:
        pipeline = [
            {"$match": match}, {"$group": {"_id": group_id, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}, {"$limit": limit}, {"$project": {project_field: "$_id", "count": 1, "_id": 0}},
        ]
        return await self._run(col, pipeline)

    async def _yield_trend(self, col, match: dict, trend: str) -> list:
        if trend == "week":
            group_id = {
                "year": {"$isoWeekYear": {"$dateFromString": {"dateString": "$test_time"}}},
                "week": {"$isoWeek": {"$dateFromString": {"dateString": "$test_time"}}},
            }
            pipeline = [
                {"$match": match},
                {"$group": {"_id": group_id, "total": {"$sum": 1},
                            "passed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "成功"]}, 1, 0]}},
                            "failed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "失败"]}, 1, 0]}}}},
                {"$sort": {"_id.year": 1, "_id.week": 1}},
                {"$project": {"date": {"$concat": [{"$toString": "$_id.year"}, "-W", {"$toString": "$_id.week"}]},
                              "total": 1, "passed": 1, "failed": 1,
                              "yield": {"$cond": [{"$gt": ["$total", 0]},
                                                  {"$round": [{"$multiply": [{"$divide": ["$passed", "$total"]}, 100]}, 1]}, 0]},
                              "_id": 0}},
            ]
        else:
            n = 7 if trend == "month" else 10
            pipeline = [
                {"$match": match},
                {"$group": {"_id": {"$substr": ["$test_time", 0, n]}, "total": {"$sum": 1},
                            "passed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "成功"]}, 1, 0]}},
                            "failed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "失败"]}, 1, 0]}}}},
                {"$sort": {"_id": 1}},
                {"$project": {"date": "$_id", "total": 1, "passed": 1, "failed": 1,
                              "yield": {"$cond": [{"$gt": ["$total", 0]},
                                                  {"$round": [{"$multiply": [{"$divide": ["$passed", "$total"]}, 100]}, 1]}, 0]},
                              "_id": 0}},
            ]
        return await self._run(col, pipeline)

    async def _model_defects(self, details, servers, match: dict) -> list:
        pipeline = [
            {"$match": match},
            {"$lookup": {"from": "sync_remote_servers", "localField": "server_sn", "foreignField": "server_sn", "as": "info"}},
            {"$unwind": "$info"}, {"$match": {"info.product_models": {"$ne": ""}}},
            {"$group": {"_id": "$info.product_models", "total": {"$sum": 1},
                        "failed": {"$sum": {"$cond": [{"$eq": ["$server_test_result", "失败"]}, 1, 0]}},
                        "latest": {"$max": "$test_time"}}},
            {"$sort": {"latest": -1}}, {"$limit": 10},
            {"$project": {"model": "$_id", "total": 1, "failed": 1,
                          "yield": {"$cond": [{"$gt": ["$total", 0]},
                                              {"$round": [{"$multiply": [{"$divide": [{"$subtract": ["$total", "$failed"]}, "$total"]}, 100]}, 1]}, 0]},
                          "_id": 0}},
        ]
        return await self._run(details, pipeline)

    @staticmethod
    async def _run(col, pipeline: list) -> list:
        for attempt in range(3):
            try:
                return await col.aggregate(pipeline, allowDiskUse=True).to_list(length=1000)
            except OperationFailure as e:
                # Index dropped/rebuilt during startup or reload (code 175 QueryPlanKilled)
                if e.code == 175 and attempt < 2:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                logging.error("Aggregation failed: %s", e)
                return []
            except Exception as e:
                logging.error("Aggregation failed: %s", e)
                return []
        return []

    async def _loop(self):
        await self.refresh_all()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=3600.0)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            if not self._stop.is_set():
                await self.refresh_all()

    def start(self):
        if not self._task or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._loop())

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def stop(self):
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
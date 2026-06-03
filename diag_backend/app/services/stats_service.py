"""
Stats Service — 从预计算统计摘要 (test_stats_daily) 读取看板数据

替代从 sync_remote_test_details 实时聚合的方式，直接读取每日预计算结果，
大幅降低查询延迟和 MongoDB 聚合开销。
"""
import logging
from collections import defaultdict
from datetime import timedelta
from typing import Optional

from ..core.utils import utc_now
from ..core.mongodb import get_collection

logger = logging.getLogger(__name__)

STATS_COLLECTION = "test_stats_daily"


def get_stats_service() -> "StatsService":
    return StatsService()


class StatsService:

    async def get_daily_stats(
        self,
        factory_id: Optional[str] = None,
        days: int = 30,
    ) -> list[dict]:
        """获取每日统计列表"""
        col = get_collection(STATS_COLLECTION)
        match: dict = {}
        if factory_id:
            match["factory_id"] = factory_id

        # 只取最近 N 天的数据
        cutoff = (utc_now() - timedelta(days=days)).strftime("%Y-%m-%d")
        match["date"] = {"$gte": cutoff}

        cursor = col.find(
            match,
            {"_id": 0, "type": 0},
        ).sort("date", -1).limit(days)

        return await cursor.to_list(length=days)

    async def get_summary(
        self,
        factory_id: Optional[str] = None,
        days: int = 30,
    ) -> dict:
        """获取汇总统计（跨日聚合）"""
        daily = await self.get_daily_stats(factory_id, days)
        if not daily:
            return {}

        total = sum(d.get("stats", {}).get("total", 0) for d in daily)
        passed = sum(d.get("stats", {}).get("passed", 0) for d in daily)
        failed = sum(d.get("stats", {}).get("failed", 0) for d in daily)

        # 合并 fault_categories (去重累加)
        merged_categories: dict[str, int] = {}
        merged_subcategories: dict[str, int] = {}
        merged_decision: dict[str, int] = {}
        merged_station: dict[str, int] = {}
        merged_models: dict[str, dict] = {}

        def _merge_labeled(
            merged: dict[str, int],
            items: list,
            *label_keys: str,
        ) -> None:
            for item in items:
                if not isinstance(item, dict):
                    continue
                label = next((item[k] for k in label_keys if item.get(k)), None)
                if not label:
                    continue
                merged[label] = merged.get(label, 0) + item.get("count", 0)

        for d in daily:
            stats = d.get("stats", {})
            for item in stats.get("fault_categories", []):
                merged_categories[item["name"]] = merged_categories.get(item["name"], 0) + item["count"]
            for item in stats.get("fault_subcategories", []):
                merged_subcategories[item["name"]] = merged_subcategories.get(item["name"], 0) + item["count"]
            # compute_test_stats 曾用 _top10 写入 name 字段，兼容 decision / station 两种键
            _merge_labeled(merged_decision, stats.get("decision_distribution", []), "decision", "name")
            _merge_labeled(merged_station, stats.get("station_failures", []), "station", "name")
            for item in stats.get("model_defects", []):
                m = item["model"]
                if m not in merged_models:
                    merged_models[m] = {"total": 0, "failed": 0,
                                        "station_failures": defaultdict(int),
                                        "fault_categories": defaultdict(int)}
                merged_models[m]["total"] += item["total"]
                merged_models[m]["failed"] += item["failed"]
                for sf in item.get("station_failures", []):
                    st = sf.get("station") or sf.get("name")
                    if st:
                        merged_models[m]["station_failures"][st] += sf.get("count", 0)
                for fc in item.get("fault_categories", []):
                    merged_models[m]["fault_categories"][fc["name"]] += fc["count"]

        def _top10_named(counter: dict[str, int]) -> list[dict]:
            return [{"name": k, "count": v} for k, v in sorted(counter.items(), key=lambda x: -x[1])[:10]]

        def _top10_labeled(counter: dict[str, int], label_key: str) -> list[dict]:
            return [{label_key: k, "count": v} for k, v in sorted(counter.items(), key=lambda x: -x[1])[:10]]

        model_defects = [
            {"model": m, "total": s["total"], "failed": s["failed"],
             "yield": round((s["total"] - s["failed"]) / s["total"] * 100, 1) if s["total"] > 0 else 0,
             "station_failures": _top10_labeled(s["station_failures"], "station"),
             "fault_categories": _top10_named(s["fault_categories"])}
            for m, s in sorted(merged_models.items(), key=lambda x: -x[1]["total"])[:10]
        ]

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "avg_yield": round(passed / total * 100, 1) if total > 0 else 0,
            "total_days": len(daily),
            "fault_categories": _top10_named(merged_categories),
            "fault_subcategories": _top10_named(merged_subcategories),
            "station_failures": _top10_labeled(merged_station, "station"),
            "decision_distribution": _top10_labeled(merged_decision, "decision"),
            "model_defects": model_defects,
        }

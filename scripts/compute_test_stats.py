#!/usr/bin/env python3
"""
预计算统计摘要 — 从 sync_remote_test_details 聚合数据到 test_stats_daily

从原始测试详情中按 (厂区, 日期) 分组，预计算看板所需的 6 组聚合数据，
大幅减少 MongoDB 实时聚合开销。

用法:
    python scripts/compute_test_stats.py                    # 增量计算所有厂区
    python scripts/compute_test_stats.py --factory kunshan  # 指定厂区
    python scripts/compute_test_stats.py --hours 48         # 仅计算最近 48h
    python scripts/compute_test_stats.py --full              # 全量重新计算
    python scripts/compute_test_stats.py --dry-run           # 试运行
"""
import argparse
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from pymongo import MongoClient, UpdateOne

# ─── 日志 ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("compute_stats")

# ─── 常量 ──────────────────────────────────────────────
MONGODB_URI = "mongodb://10.17.154.252:27018"
MONGODB_DB = "diag_analysis"
DEFAULT_DAYS = 7
BATCH_SIZE = 5000


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="预计算看板统计摘要")
    p.add_argument("--mongodb-uri", default=MONGODB_URI)
    p.add_argument("--mongodb-db", default=MONGODB_DB)
    p.add_argument("--factory", type=str, default=None, help="仅计算指定厂区")
    p.add_argument("--hours", type=int, default=None,
                   help="仅计算最近 N 小时（首次部署时用，不传则增量）")
    p.add_argument("--full", action="store_true", help="全量重新计算，忽略增量标记")
    p.add_argument("--dry-run", action="store_true", help="试运行，不写入数据库")
    p.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    return p.parse_args()


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date(s: str) -> str:
    """从 ISO 时间戳提取日期部分"""
    if s and len(s) >= 10:
        return s[:10]
    return s


# ─── 核心聚合逻辑 ──────────────────────────────────────


def compute_day_stats(
    details: list[dict],
    servers_lookup: dict[str, dict],
) -> dict:
    """对一整天 + 一个厂区的原始数据执行 6 组聚合，返回 stats 文档"""
    total = len(details)
    passed = 0
    failed = 0

    fault1_counter: dict[str, int] = defaultdict(int)
    fault2_counter: dict[str, int] = defaultdict(int)
    station_fail_counter: dict[str, int] = defaultdict(int)
    decision_counter: dict[str, int] = defaultdict(int)
    model_stats: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "failed": 0, "fault_categories": defaultdict(int),
                  "station_failures": defaultdict(int)}
    )

    for d in details:
        result = d.get("server_test_result", "")
        if result == "成功":
            passed += 1
        elif result == "失败":
            failed += 1

        # fault_type1 (主类别)
        ft1 = d.get("fault_type1", "")
        if ft1:
            fault1_counter[ft1] += 1

        # fault_type2 (子类别)
        ft2 = d.get("fault_type2", "")
        if ft2:
            fault2_counter[ft2] += 1

        # station (detailed_flow)
        flow = d.get("detailed_flow", "")
        if flow and result == "失败":
            station_fail_counter[flow] += 1

        # decision
        dec = d.get("decision", "")
        if dec:
            decision_counter[dec] += 1

        # model (通过 server_sn 关联)
        sn = d.get("server_sn", "")
        if sn and sn in servers_lookup:
            model = servers_lookup[sn].get("product_models", "") or servers_lookup[sn].get("model", "")
            if model:
                model_stats[model]["total"] += 1
                if result == "失败":
                    model_stats[model]["failed"] += 1
                # 机型内部细分的工站不良和根因
                if flow:
                    model_stats[model]["station_failures"][flow] += 1
                if ft1:
                    model_stats[model]["fault_categories"][ft1] += 1

    def _top10_name(counter: dict[str, int]) -> list[dict]:
        return [{"name": k, "count": v} for k, v in sorted(counter.items(), key=lambda x: -x[1])[:10]]

    def _top10_station(counter: dict[str, int]) -> list[dict]:
        return [{"station": k, "count": v} for k, v in sorted(counter.items(), key=lambda x: -x[1])[:10]]

    def _top10_decision(counter: dict[str, int]) -> list[dict]:
        return [{"decision": k, "count": v} for k, v in sorted(counter.items(), key=lambda x: -x[1])[:10]]

    model_defects = []
    for model, ms in sorted(model_stats.items(), key=lambda x: -x[1]["total"]):
        t = ms["total"]
        f = ms["failed"]
        model_defects.append({
            "model": model,
            "total": t,
            "failed": f,
            "yield": round((t - f) / t * 100, 1) if t > 0 else 0,
            "station_failures": _top10_station(ms["station_failures"]),
            "fault_categories": _top10_name(ms["fault_categories"]),
        })

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "fault_categories": _top10_name(fault1_counter),
        "fault_subcategories": _top10_name(fault2_counter),
        "station_failures": _top10_station(station_fail_counter),
        "decision_distribution": _top10_decision(decision_counter),
        "model_defects": model_defects[:10],
    }


# ─── 引擎 ──────────────────────────────────────────────


def compute_all(
    db,
    factories: list[str],
    since: Optional[datetime] = None,
    full_recompute: bool = False,
    dry_run: bool = False,
) -> dict:
    """主聚合流程"""
    details_col = db["sync_remote_test_details"]
    servers_col = db["sync_remote_servers"]
    stats_col = db["test_stats_daily"]
    meta_col = db["_computed_meta"]

    total_days = 0
    total_records_processed = 0

    # 为增量模式读取每台服务器的 model 缓存
    logger.info("加载服务器型号信息...")
    server_models: dict[str, dict] = {}
    for srv in servers_col.find({}, {"server_sn": 1, "product_models": 1, "model": 1}):
        server_models[srv["server_sn"]] = srv

    # 收集所有待处理厂区
    if factories:
        factory_list = factories
    else:
        factory_list = db["sync_remote_test_details"].distinct("factory_id")
        factory_list = [f for f in factory_list if f]

    if not factory_list:
        logger.warning("未找到任何厂区数据")
        return {"days": 0, "records": 0}

    logger.info("待处理厂区: %s", ", ".join(factory_list))

    for fid in factory_list:
        # 确定时间范围
        if full_recompute:
            ts_since = None
        elif since:
            ts_since = since.isoformat()
        else:
            meta = meta_col.find_one({"collection": "test_stats_daily", "factory_id": fid})
            if meta and meta.get("last_computed_at"):
                ts_since = meta["last_computed_at"]
                logger.info("[%s] 增量模式，上次计算时间: %s", fid, ts_since)
            else:
                ts_since = None

        # 分批读取原始数据
        match: dict = {"factory_id": fid}
        if ts_since:
            match["test_time"] = {"$gte": ts_since}

        total = details_col.count_documents(match)
        if total == 0:
            logger.info("[%s] 无新数据需要计算", fid)
            continue
        logger.info("[%s] 待处理 %d 条原始记录", fid, total)

        # 按 (日期, factory_id) 分组的内存聚合
        day_buckets: dict[str, list[dict]] = defaultdict(list)
        last_test_time = ts_since or ""
        cursor = details_col.find(
            match,
            {
                "factory_id": 1, "server_sn": 1, "server_test_result": 1,
                "fault_type1": 1, "fault_type2": 1, "detailed_flow": 1,
                "decision": 1, "test_time": 1,
            },
            no_cursor_timeout=True,
        ).batch_size(BATCH_SIZE)

        batch_count = 0
        for doc in cursor:
            dt = _parse_date(doc.get("test_time", ""))
            if dt:
                day_buckets[dt].append(doc)

            tt = doc.get("test_time", "")
            if tt and tt > last_test_time:
                last_test_time = tt

            batch_count += 1
            if batch_count % BATCH_SIZE == 0:
                logger.debug("[%s] 已扫描 %d 条...", fid, batch_count)

        cursor.close()

        if not day_buckets:
            logger.info("[%s] 按日期分组后无有效数据，跳过", fid)
            continue

        logger.info("[%s] 按日期分组: %d 天", fid, len(day_buckets))

        # 聚合每组
        ops: list[UpdateOne] = []
        for date_str in sorted(day_buckets.keys()):
            docs = day_buckets[date_str]
            stats = compute_day_stats(docs, server_models)
            doc_id = f"daily:{fid}:{date_str}"

            if not dry_run:
                ops.append(UpdateOne(
                    {"_id": doc_id},
                    {"$set": {
                        "type": "daily",
                        "factory_id": fid,
                        "date": date_str,
                        "computed_at": _utc_now_iso(),
                        "stats": stats,
                    }},
                    upsert=True,
                ))

            total_days += 1
            total_records_processed += len(docs)

        # 批量写入
        if ops and not dry_run:
            stats_col.bulk_write(ops, ordered=False)
            logger.info("[%s] 已写入 %d 天统计 (处理 %d 条原始记录)",
                        fid, len(ops), total_records_processed)
        elif dry_run:
            logger.info("[%s] [DRY RUN] 将写入 %d 天统计 (处理 %d 条原始记录)",
                        fid, len(ops), total_records_processed)

        # 更新增量标记
        if last_test_time and not dry_run:
            meta_col.update_one(
                {"collection": "test_stats_daily", "factory_id": fid},
                {"$set": {
                    "collection": "test_stats_daily",
                    "factory_id": fid,
                    "last_computed_at": last_test_time,
                    "updated_at": _utc_now_iso(),
                }},
                upsert=True,
            )
            logger.info("[%s] 增量标记已更新: %s", fid, last_test_time)

    return {"days": total_days, "records": total_records_processed}


# ─── CLI ────────────────────────────────────────────────


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("📊 预计算看板统计摘要")
    logger.info("   db:      %s/%s", args.mongodb_uri, args.mongodb_db)
    logger.info("   factory: %s", args.factory or "ALL")
    logger.info("   full:    %s", args.full)
    logger.info("   dry-run: %s", args.dry_run)
    logger.info("   verbose: %s", args.verbose)
    if args.hours:
        logger.info("   hours:   %s", args.hours)
    logger.info("=" * 60)

    # 时间范围
    since = None
    if args.hours:
        since = datetime.now(timezone.utc) - timedelta(hours=args.hours)
        logger.info("扫描范围: 最近 %d 小时 (>= %s)", args.hours, since.isoformat())

    # 连接 MongoDB
    logger.info("连接 MongoDB...")
    mongo = MongoClient(args.mongodb_uri)
    db = mongo[args.mongodb_db]
    db.command("ping")
    logger.info("✅ MongoDB 连接成功")

    factories = [args.factory] if args.factory else []

    start = time.time()
    try:
        result = compute_all(
            db,
            factories=factories,
            since=since,
            full_recompute=args.full or bool(args.hours),
            dry_run=args.dry_run,
        )
        elapsed = time.time() - start
        logger.info("✅ 完成! 共 %d 天 / %d 条记录，耗时 %.1f 秒",
                    result["days"], result["records"], elapsed)
    except Exception as e:
        logger.exception("计算失败: %s", e)
        sys.exit(1)
    finally:
        mongo.close()


if __name__ == "__main__":
    main()

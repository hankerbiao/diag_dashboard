#!/usr/bin/env python3
"""
预计算看板统计摘要 — 从 MES API 直接拉取数据 → 聚合 → test_stats_daily

跳过原始数据大表，不再存储每条测试记录。
用法:
    python scripts/compute_test_stats.py                    # 增量计算所有厂区
    python scripts/compute_test_stats.py --factory kunshan  # 指定厂区
    python scripts/compute_test_stats.py --hours 48         # 首次：最近 48h
    python scripts/compute_test_stats.py --full              # 全量重新计算
    python scripts/compute_test_stats.py --dry-run           # 试运行
"""
import argparse
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import multiprocessing as mp

import requests
import yaml

from pymongo import MongoClient, UpdateOne

# ─── 日志 ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("compute_stats")

# ─── 常量 ──────────────────────────────────────────────
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://10.17.154.252:27018")
MONGODB_DB = os.environ.get("MONGODB_DB", "diag_analysis")
FACTORIES_YAML = os.path.join(
    os.path.dirname(__file__), "..", "diag_backend", "configs", "factories.yaml"
)
API_TIMEOUT = 30


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="预计算看板统计摘要（直连 MES API）")
    p.add_argument("--mongodb-uri", default=MONGODB_URI)
    p.add_argument("--mongodb-db", default=MONGODB_DB)
    p.add_argument("--factory", type=str, default=None, help="仅计算指定厂区")
    p.add_argument("--hours", type=int, default=None,
                   help="仅计算最近 N 小时（首次部署时用，不传则增量）")
    p.add_argument("--full", action="store_true", help="全量重新计算，忽略增量标记")
    p.add_argument("--dry-run", action="store_true", help="试运行，不写入数据库")
    p.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    return p.parse_args()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date(s: str) -> str:
    if s and len(s) >= 10:
        return s[:10]
    return s


# ─── MES API 客户端 ────────────────────────────────────


class MESClient:
    """拉取服务器列表和测试详情"""

    def __init__(self, factory: dict):
        self.factory_id = factory["factory_id"]
        self.base_url = factory["base_url"].rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/page/monitor_list.html",
        })
        self._timeout = API_TIMEOUT

    def _post(self, path: str, data: dict) -> dict:
        body = urlencode({k: v for k, v in data.items() if v is not None})
        url = f"{self.base_url}{path}"
        resp = self._session.post(url, data=body, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def fetch_all_servers(self) -> list[dict]:
        all_servers = []
        page, limit = 1, 100
        while True:
            resp = self._post(
                "/stepsmanagement/monitor/queryTestingServers.action",
                data={"page": page, "limit": limit, "customerID": "",
                      "salesReceipts": "", "orderID": "", "serverSN": "",
                      "serverState": "", "models": "", "productModels": "",
                      "testItemName": ""},
            )
            batch = resp.get("data", [])
            all_servers.extend(batch)
            if len(batch) < limit:
                break
            page += 1
        return all_servers

    def fetch_test_details(self, server_sn: str, since: Optional[str] = None
                           ) -> tuple[list[dict], Optional[str]]:
        all_data, max_time = [], None
        start, limit = 0, 500
        while True:
            resp = self._post(
                "/stepsmanagement/resultInfo/queryTestList.action",
                data={"start": start, "limit": limit,
                      "serverSN": server_sn, "customerID": ""},
            )
            batch = resp.get("data", [])
            if not batch:
                break
            for d in batch:
                t = d.get("testTime")
                if t and (max_time is None or t > max_time):
                    max_time = t
            if since:
                new_batch = [d for d in batch if (d.get("testTime") or "") > since]
                all_data.extend(new_batch)
                if len(new_batch) < len(batch):
                    break
            else:
                all_data.extend(batch)
            if len(batch) < limit:
                break
            start += limit
        return all_data, max_time

    def close(self):
        self._session.close()


# ─── 数据转换 ──────────────────────────────────────────


def _parse_datetime(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").isoformat()
        except ValueError:
            return None


def to_detail_dict(raw: dict, server_sn: str) -> dict:
    return {
        "server_sn": server_sn,
        "big_flow": raw.get("bigFlow", ""),
        "detailed_flow": raw.get("detailedFlow", ""),
        "decision": raw.get("decision", ""),
        "server_test_result": raw.get("serverTestResult", ""),
        "test_time": _parse_datetime(raw.get("testTime")),
        "fault_type1": raw.get("faultType1", ""),
        "fault_type2": raw.get("faultType2", ""),
        "fault_type3": raw.get("faultType3", ""),
    }


def to_server_model(raw: dict) -> tuple[str, str]:
    sn = raw.get("serverSN", "")
    model = raw.get("productModels", "") or raw.get("model", "")
    return sn, model


# ─── 核心聚合 ──────────────────────────────────────────


def compute_day_stats(details: list[dict], servers_lookup: dict[str, str]) -> dict:
    total, passed, failed = len(details), 0, 0
    ft1_c, ft2_c, stn_c, dec_c = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    model_s: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "failed": 0,
                 "station_failures": defaultdict(int),
                 "fault_categories": defaultdict(int)}
    )
    for d in details:
        r = d.get("server_test_result", "")
        if r == "成功": passed += 1
        elif r == "失败": failed += 1
        ft1, ft2 = d.get("fault_type1", ""), d.get("fault_type2", "")
        flow, dec = d.get("detailed_flow", ""), d.get("decision", "")
        if ft1: ft1_c[ft1] += 1
        if ft2: ft2_c[ft2] += 1
        if flow and r == "失败": stn_c[flow] += 1
        if dec: dec_c[dec] += 1
        sn = d.get("server_sn", "")
        model = servers_lookup.get(sn, "")
        if model:
            ms = model_s[model]
            ms["total"] += 1
            if r == "失败": ms["failed"] += 1
            if flow: ms["station_failures"][flow] += 1
            if ft1: ms["fault_categories"][ft1] += 1
    t10n = lambda c: [{"name": k, "count": v} for k, v in sorted(c.items(), key=lambda x: -x[1])[:10]]
    t10s = lambda c: [{"station": k, "count": v} for k, v in sorted(c.items(), key=lambda x: -x[1])[:10]]
    t10d = lambda c: [{"decision": k, "count": v} for k, v in sorted(c.items(), key=lambda x: -x[1])[:10]]
    md = []
    for m, ms in sorted(model_s.items(), key=lambda x: -x[1]["total"]):
        t, f = ms["total"], ms["failed"]
        md.append({"model": m, "total": t, "failed": f,
                    "yield": round((t - f) / t * 100, 1) if t > 0 else 0,
                    "station_failures": t10s(ms["station_failures"]),
                    "fault_categories": t10n(ms["fault_categories"])})
    return {"total": total, "passed": passed, "failed": failed,
            "fault_categories": t10n(ft1_c), "fault_subcategories": t10n(ft2_c),
            "station_failures": t10s(stn_c), "decision_distribution": t10d(dec_c),
            "model_defects": md[:10]}


# ─── 引擎 ──────────────────────────────────────────────


def load_factories(yaml_path: str) -> list[dict]:
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f).get("factories", [])


def compute_factory(client: MESClient, stats_col, meta_col,
                    since: Optional[str] = None, dry_run: bool = False) -> dict:
    fid = client.factory_id
    total_days = total_records = skipped = 0
    last_tt = since or ""

    logger.info("[%s] 拉取服务器列表...", fid)
    raw_servers = client.fetch_all_servers()
    server_models: dict[str, str] = {}
    for srv in raw_servers:
        sn, m = to_server_model(srv)
        if sn and m: server_models[sn] = m
    logger.info("[%s] %d 台服务器，%d 台有型号", fid, len(raw_servers), len(server_models))

    day_buckets: dict[str, list] = defaultdict(list)
    total_servers = len(raw_servers)
    for idx, srv in enumerate(raw_servers, 1):
        sn = srv.get("serverSN", "")
        if not sn: continue
        if idx % 50 == 0 or idx == total_servers:
            logger.debug("[%s] 服务器进度 %d/%d", fid, idx, total_servers)
        try:
            details, mt = client.fetch_test_details(sn, since)
            if not details: skipped += 1; continue
            for d in details:
                dt = _parse_date(d.get("testTime", ""))
                if dt: day_buckets[dt].append(to_detail_dict(d, sn))
            if mt and mt > last_tt: last_tt = mt
        except Exception as e:
            logger.warning("[%s] %s 拉取失败: %s", fid, sn, e)

    if not day_buckets:
        logger.info("[%s] 无新数据 (%d 台跳过)", fid, skipped)
        return {"days": 0, "records": 0, "skipped": skipped}

    logger.info("[%s] %d 台, %d 天, %d 台跳过", fid, len(raw_servers)-skipped, len(day_buckets), skipped)
    ops = []
    for date_str in sorted(day_buckets):
        stats = compute_day_stats(day_buckets[date_str], server_models)
        if not dry_run:
            ops.append(UpdateOne(
                {"_id": f"daily:{fid}:{date_str}"},
                {"$set": {"type": "daily", "factory_id": fid, "date": date_str,
                          "computed_at": _utc_now_iso(), "stats": stats}},
                upsert=True))
        total_days += 1
        total_records += len(day_buckets[date_str])

    if ops and not dry_run:
        stats_col.bulk_write(ops, ordered=False)
    if last_tt and not dry_run:
        meta_col.update_one(
            {"collection": "test_stats_daily", "factory_id": fid},
            {"$set": {"collection": "test_stats_daily", "factory_id": fid,
                      "last_computed_at": last_tt, "updated_at": _utc_now_iso()}},
            upsert=True)
    logger.info("[%s] 完成: %d 天 / %d 条", fid, total_days, total_records)
    return {"days": total_days, "records": total_records, "skipped": skipped}


# ─── 多进程 Worker ──────────────────────────────────────────


def _compute_one_factory(args: tuple) -> dict:
    """在子进程中计算单个厂区的统计（独立 MongoDB 连接）"""
    factory, since, mongodb_uri, mongodb_db, dry_run = args
    fid = factory["factory_id"]

    t0 = time.time()
    logger.info("[%s] [Worker] 开始处理", fid)

    mongo = MongoClient(mongodb_uri)
    db = mongo[mongodb_db]
    meta_col = db["_computed_meta"]
    stats_col = db["test_stats_daily"]
    client = MESClient(factory)
    try:
        result = compute_factory(client, stats_col, meta_col,
                                 since=since, dry_run=dry_run)
        elapsed = time.time() - t0
        logger.info("[%s] [Worker] 完成 (%.1f 秒): %d 天 / %d 条",
                     fid, elapsed, result.get("days", 0), result.get("records", 0))
        return result
    except Exception as e:
        logger.exception("[%s] [Worker] 失败: %s", fid, e)
        return {"days": 0, "records": 0, "skipped": 0}
    finally:
        client.close()
        mongo.close()


# ─── CLI ────────────────────────────────────────────────


def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG); logger.setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("📊 预计算看板统计摘要（直连 MES API）")
    logger.info("   factories: %s", FACTORIES_YAML)
    logger.info("   db:   %s/%s", args.mongodb_uri, args.mongodb_db)
    logger.info("   factory: %s", args.factory or "ALL")
    logger.info("   dry-run: %s | full: %s", args.dry_run, args.full)
    if args.hours: logger.info("   hours: %s", args.hours)
    logger.info("=" * 60)

    factories = load_factories(FACTORIES_YAML)
    if args.factory:
        factories = [f for f in factories if f["factory_id"] == args.factory]
    if not factories: logger.error("无厂区配置"); sys.exit(1)
    logger.info("厂区: %s", ", ".join(f["factory_id"] for f in factories))

    since = None
    if args.hours:
        since = (datetime.now(timezone.utc) - timedelta(hours=args.hours)).isoformat()
        logger.info("最近 %dh (>= %s)", args.hours, since)

    total_stats = {"days": 0, "records": 0, "skipped": 0}
    start_t = time.time()

    # 预先查询每个厂区的增量起始时间
    process_args = []
    mongo = MongoClient(args.mongodb_uri); db = mongo[args.mongodb_db]
    for fc in factories:
        fid = fc["factory_id"]
        ts = since
        if not ts and not args.full:
            m = db["_computed_meta"].find_one(
                {"collection": "test_stats_daily", "factory_id": fid}
            )
            if m and m.get("last_computed_at"):
                ts = m["last_computed_at"]
                logger.debug("[%s] 增量起始: %s", fid, ts)
        process_args.append((fc, ts, args.mongodb_uri, args.mongodb_db, args.dry_run))
    mongo.close()

    n_factories = len(process_args)
    if n_factories == 1:
        logger.info("单厂区，直接执行")
        results = [_compute_one_factory(process_args[0])]
    else:
        n_workers = min(n_factories, mp.cpu_count())
        logger.info("多进程并行: %d 个厂区, %d 个工作进程", n_factories, n_workers)
        with mp.Pool(n_workers) as pool:
            results = pool.map(_compute_one_factory, process_args)

    for r in results:
        for k in total_stats:
            total_stats[k] += r.get(k, 0)

    elapsed = time.time() - start_t
    logger.info("=" * 60)
    logger.info("✅ 完成! %d 天 / %d 条 (%d 台跳过) %.1f 秒",
                total_stats["days"], total_stats["records"],
                total_stats["skipped"], elapsed)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
独立数据同步脚本

从 YAML 配置文件中读取所有厂区配置，依次对接各厂区的 MES API，
拉取近 N 小时（可配置）的测试数据并写入 MongoDB。

用法:
    python scripts/sync_data.py                          # 默认近 24 小时
    python scripts/sync_data.py --hours 48               # 近 48 小时
    python scripts/sync_data.py --hours 0                # 全量同步
    python scripts/sync_data.py --factory kunshan        # 仅同步指定厂区
    python scripts/sync_data.py --dry-run                # 试运行（只拉取不写入）

日志环境变量:
    SYNC_LOG_LEVEL=DEBUG         # 日志级别
    SYNC_LOG_DIR=./logs          # 日志目录
    SYNC_LOG_JSON=false          # JSON 格式输出
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import requests
import yaml

# 导入统一日志模块
from sync_logger import (
    setup_logger, get_logger, log_sync_start, log_sync_complete, log_sync_error,
    log_factory_start, log_factory_complete, log_api_call, log_step,
    log_warning, log_debug, TRACE_ID
)

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore[assignment]

# 初始化日志
logger = setup_logger("sync_data")


# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "diag_backend", "configs", "factories.yaml"
)
DEFAULT_MONGODB_URI = os.environ.get(
    "MONGODB_URI", "mongodb://10.17.154.252:27018"
)
DEFAULT_MONGODB_DB = os.environ.get("MONGODB_DB", "diag_analysis")
DEFAULT_HOURS = 24
DEFAULT_TIMEOUT = 30

# 脚本标识
SCRIPT_NAME = "sync_data"


# ──────────────────────────────────────────────
# MongoDB 写入
# ──────────────────────────────────────────────

try:
    from pymongo import MongoClient, UpdateOne
except ImportError:
    logger.error("需要 pymongo: pip install pymongo")
    sys.exit(1)


# ──────────────────────────────────────────────
# 进度条辅助
# ──────────────────────────────────────────────

def _progress(iterable=None, desc="", total=None, unit="", leave=True, **kwargs):
    """tqdm 包装器，未安装时退化为普通迭代"""
    if tqdm is not None:
        return tqdm(iterable, desc=desc, total=total, unit=unit, leave=leave, **kwargs)
    return iterable or []


def _write(msg: str):
    """tqdm.write 或 print，避免日志与进度条冲突"""
    if tqdm is not None:
        tqdm.write(msg)
    else:
        print(msg)


# ──────────────────────────────────────────────
# 数据抓取
# ──────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MESClient:
    """MES API 客户端"""

    def __init__(self, factory: dict, timeout: int = DEFAULT_TIMEOUT):
        self.factory_id = factory["factory_id"]
        self.base_url = factory["base_url"].rstrip("/")
        self.log_base_url = (factory.get("log_base_url") or "").rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/page/monitor_list.html",
            "X-Trace-ID": TRACE_ID,
        })
        self._timeout = timeout
        self._client_logger = get_logger(f"sync_data.{self.factory_id}")

    def post(self, path: str, data: dict) -> dict:
        body = urlencode({k: v for k, v in data.items() if v is not None})
        url = f"{self.base_url}{path}"
        start_time = time.time()
        try:
            resp = self._session.post(url, data=body, timeout=self._timeout)
            duration_ms = (time.time() - start_time) * 1000
            resp.raise_for_status()
            result = resp.json()
            log_api_call(url, "POST", resp.status_code, len(result.get("data", [])), duration_ms)
            return result
        except requests.RequestException as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call(url, "POST", status_code=500, duration_ms=duration_ms, error=str(e))
            self._client_logger.error(f"API 请求失败: {path} - {e}")
            raise

    def fetch_all_servers(self) -> list[dict]:
        """分页拉取所有服务器列表"""
        all_servers = []
        page = 1
        limit = 100
        total_fetched = 0
        while True:
            resp = self.post(
                "/stepsmanagement/monitor/queryTestingServers.action",
                data={
                    "page": page, "limit": limit,
                    "customerID": "", "salesReceipts": "", "orderID": "",
                    "serverSN": "", "serverState": "", "models": "",
                    "productModels": "", "testItemName": "",
                },
            )
            batch = resp.get("data", [])
            all_servers.extend(batch)
            total_fetched += len(batch)
            log_debug(f"服务器列表 page {page}: {len(batch)} 条", factory_id=self.factory_id)
            if len(batch) < limit:
                break
            page += 1
        log_step("服务器列表拉取完成", f"共 {total_fetched} 台", total_fetched)
        return all_servers

    def fetch_test_details(self, server_sn: str, since: Optional[str] = None) -> tuple[list[dict], Optional[str]]:
        """拉取一台服务器的测试详情"""
        all_data = []
        start = 0
        limit = 500
        max_time: Optional[str] = None

        while True:
            resp = self.post(
                "/stepsmanagement/resultInfo/queryTestList.action",
                data={"start": start, "limit": limit, "serverSN": server_sn, "customerID": ""},
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


# ──────────────────────────────────────────────
# 数据转换
# ──────────────────────────────────────────────

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


def to_server_record(raw: dict, factory_id: str) -> dict:
    def _str(v, default=""):
        if v is None:
            return default
        if isinstance(v, (dict, list)):
            return str(v)
        return str(v)

    return {
        "factory_id": factory_id,
        "server_sn": _str(raw.get("serverSN")),
        "order_id": _str(raw.get("orderID")),
        "model": _str(raw.get("model")),
        "product_models": _str(raw.get("productModels")),
        "host_ip": _str(raw.get("hostIP")),
        "bmc_ip4": _str(raw.get("bmcIP4")),
        "bmc_ip6": _str(raw.get("bmcIP6")),
        "position": _str(raw.get("position")),
        "logical": _str(raw.get("logical")),
        "alarm": int(raw.get("alarm") or 0),
        "server_state": _str(raw.get("serverState")),
        "test_items": _str(raw.get("testItems")),
        "next_item": _str(raw.get("nextItem")),
        "item_begin_time": _parse_datetime(raw.get("itemBeginTime")),
        "customer_id": _str(raw.get("customerID")),
        "customer_name": _str(raw.get("customerName")),
        "sales_receipts": _str(raw.get("salesReceipts")),
        "promised_date": _str(raw.get("promisedDate")),
        "maintenance_status": _str(raw.get("maintenanceStatus")),
        "final_operation": _str(raw.get("finalOperation")),
        "customized_system": _str(raw.get("customizedSystem")),
        "synced_at": _now_iso(),
    }


def to_detail_record(server_id: str, server_sn: str, factory_id: str, raw: dict) -> dict:
    return {
        "factory_id": factory_id,
        "server_id": server_id,
        "server_sn": server_sn,
        "big_flow": raw.get("bigFlow", ""),
        "detailed_flow": raw.get("detailedFlow", ""),
        "log_path": raw.get("log", ""),
        "decision": raw.get("decision", ""),
        "server_test_result": raw.get("serverTestResult", ""),
        "test_time": _parse_datetime(raw.get("testTime")),
        "mes_record": raw.get("mesRecord", ""),
        "fault_type1": raw.get("faultType1", ""),
        "fault_type2": raw.get("faultType2", ""),
        "fault_type3": raw.get("faultType3", ""),
        "mes_remarks": raw.get("mesRemarks", ""),
        "mes_time": _parse_datetime(raw.get("mesTime")),
        "synced_at": _now_iso(),
    }


# ──────────────────────────────────────────────
# 同步引擎
# ──────────────────────────────────────────────

def sync_factory(
    client: MESClient,
    db,
    hours: int,
    dry_run: bool = False,
) -> dict:
    """同步单个厂区数据"""
    factory_id = client.factory_id
    factory_logger = get_logger(f"sync_data.{factory_id}")
    start_time = time.time()

    # 记录厂区同步开始
    log_factory_start(factory_id, hours=hours, dry_run=dry_run, mode="全量" if hours == 0 else "增量")

    servers_col = db["sync_remote_servers"]
    details_col = db["sync_remote_test_details"]

    servers_new = 0
    details_total = 0
    details_new = 0

    # Step 1: 拉取服务器列表
    _write(f"[{factory_id}] 拉取服务器列表...")
    factory_logger.info("开始拉取服务器列表")
    all_servers = client.fetch_all_servers()

    # 增量模式：读取已有 last_test_time
    existing_times: dict[str, str] = {}
    if hours > 0:
        cursor = servers_col.find(
            {"server_sn": {"$in": [s.get("serverSN", "") for s in all_servers]},
             "factory_id": factory_id},
            {"server_sn": 1, "last_test_time": 1}
        )
        for doc in cursor:
            t = doc.get("last_test_time")
            if t:
                existing_times[doc["server_sn"]] = t
        log_debug(f"读取到 {len(existing_times)} 台服务器的历史同步时间", factory_id=factory_id)

    # 数据年龄截止
    cutoff_dt = None
    if hours > 0:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        _write(f"  [{factory_id}] 数据截止时间: {cutoff_dt.isoformat()[:19]} ({hours}h)")
        log_debug(f"数据截止时间: {cutoff_dt.isoformat()[:19]}", factory_id=factory_id)

    # Upsert 服务器
    _write(f"[{factory_id}] 写入服务器列表 ({len(all_servers)} 台)...")
    log_step("开始写入服务器列表", f"{len(all_servers)} 台", len(all_servers))
    sn_to_id: dict[str, str] = {}
    for raw in _progress(all_servers, desc="写入服务器", unit="台", leave=False):
        record = to_server_record(raw, factory_id)
        if dry_run:
            sn_to_id[record["server_sn"]] = f"dry-run-{record['server_sn']}"
            continue

        result = servers_col.update_one(
            {"server_sn": record["server_sn"], "factory_id": factory_id},
            {"$set": record},
            upsert=True,
        )
        if result.upserted_id:
            servers_new += 1
            sn_to_id[record["server_sn"]] = str(result.upserted_id)
        else:
            existing = servers_col.find_one(
                {"server_sn": record["server_sn"], "factory_id": factory_id}
            )
            if existing:
                sn_to_id[record["server_sn"]] = str(existing["_id"])

    _write(f"  [{factory_id}] 服务器同步完毕: {len(sn_to_id)} 台 (新增 {servers_new})")
    log_step("服务器列表写入完成", f"总计: {len(sn_to_id)} 台, 新增: {servers_new}", servers_new)

    # Step 2: 拉取测试详情
    mode = "全量" if hours == 0 else "增量"
    total_servers = len(sn_to_id)
    _write(f"[{factory_id}] [{mode}] 拉取 {total_servers} 台服务器测试详情...")
    factory_logger.info(f"开始拉取测试详情 (模式: {mode}, 服务器: {total_servers} 台)")
    skipped_servers = 0

    pbar = _progress(sn_to_id.items(), desc="拉取测试详情", unit="台", total=total_servers)
    for sn, sid in pbar:
        try:
            since = None if hours == 0 else existing_times.get(sn)
            if cutoff_dt:
                cutoff_iso = cutoff_dt.isoformat()
                if since is None or since < cutoff_iso:
                    since = cutoff_iso

            # 跳过：服务器已有数据且在截止时间内，无需调用 MES API
            if hours > 0 and sn in existing_times and cutoff_dt and existing_times[sn] >= cutoff_iso:
                skipped_servers += 1
                if tqdm is not None:
                    pbar.set_postfix_str("已是最新")
                continue

            details, new_max_time = client.fetch_test_details(sn, since)
            if since and not details:
                skipped_servers += 1
                if tqdm is not None:
                    pbar.set_postfix_str("跳过")
                continue

            if not dry_run:
                ops = []
                for detail in details:
                    record = to_detail_record(sid, sn, factory_id, detail)
                    ops.append(
                        UpdateOne(
                            {
                                "server_id": sid,
                                "factory_id": factory_id,
                                "detailed_flow": record["detailed_flow"],
                                "test_time": record["test_time"],
                            },
                            {"$set": record},
                            upsert=True,
                        )
                    )
                if ops:
                    details_col.bulk_write(ops, ordered=False)

            details_total += len(details)

            # 更新 last_test_time
            if new_max_time and not dry_run:
                servers_col.update_one(
                    {"server_sn": sn, "factory_id": factory_id},
                    {"$set": {"last_test_time": new_max_time}},
                )

            if tqdm is not None:
                pbar.set_postfix_str(f"{len(details)}条")
        except Exception as e:
            factory_logger.error(f"同步服务器 {sn} 失败: {e}")
            log_warning(f"同步服务器 {sn} 失败", factory_id=factory_id, server_sn=sn, error=str(e))

    duration_ms = (time.time() - start_time) * 1000
    result = {
        "factory_id": factory_id,
        "servers_total": len(sn_to_id),
        "servers_new": servers_new,
        "details_total": details_total,
        "details_new": details_total,
        "skipped_servers": skipped_servers,
    }
    _write(
        f"  [{factory_id}] [{mode}] 完成: {result['servers_total']} 台服务器, "
        f"{details_total} 条详情"
        + (f", {skipped_servers} 台跳过" if skipped_servers else "")
    )

    # 记录厂区同步完成
    log_factory_complete(factory_id, len(sn_to_id), details_total, skipped_servers, duration_ms,
                         servers_new=servers_new, mode=mode, hours=hours)

    return result


def save_job(db, status: str, factory_id: str, result: dict, error_message: str = ""):
    """记录同步任务执行历史"""
    job_doc = {
        "status": status,
        "factory_id": factory_id,
        "started_at": _now_iso(),
        "servers_total": result.get("servers_total", 0),
        "servers_new": result.get("servers_new", 0),
        "details_total": result.get("details_total", 0),
        "details_new": result.get("details_new", 0),
        "error_message": error_message,
    }
    db["sync_jobs"].insert_one(job_doc)
    log_debug("同步任务记录已保存", factory_id=factory_id, status=status)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def load_config(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    factories = data.get("factories", [])
    if not factories:
        logger.error("配置文件中未找到 factories 定义")
        sys.exit(1)
    logger.info("Loaded %d factories from %s", len(factories), path)
    return factories


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="WeaveEye 独立数据同步脚本 — 从各厂区 MES API 抓取数据写入 MongoDB",
    )
    parser.add_argument(
        "--config", "-c",
        default=DEFAULT_CONFIG_PATH,
        help=f"厂区配置文件路径 (默认: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--hours", type=int, default=DEFAULT_HOURS,
        help=f"同步最近 N 小时的数据 (默认: {DEFAULT_HOURS}, 0=全量)",
    )
    parser.add_argument(
        "--factory", "-f", type=str, default=None,
        help="仅同步指定厂区 (factory_id，不传则同步所有)",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="试运行模式：只拉取数据，不写入数据库",
    )
    parser.add_argument(
        "--mongodb-uri",
        default=DEFAULT_MONGODB_URI,
        help=f"MongoDB 连接 URI (默认: {DEFAULT_MONGODB_URI})",
    )
    parser.add_argument(
        "--mongodb-db",
        default=DEFAULT_MONGODB_DB,
        help=f"MongoDB 数据库名 (默认: {DEFAULT_MONGODB_DB})",
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help=f"HTTP 请求超时秒数 (默认: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="详细日志输出",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # 日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    start_time = time.time()

    # 记录同步开始
    logger.info("=" * 60)
    logger.info("🔄 WeaveEye 数据同步")
    logger.info("  trace_id: %s", TRACE_ID)
    logger.info("  hours:    %s", f"{args.hours}h" if args.hours > 0 else "FULL")
    logger.info("  factory:  %s", args.factory or "ALL")
    logger.info("  dry-run:  %s", args.dry_run)
    logger.info("  verbose:  %s", args.verbose)
    logger.info("=" * 60)
    log_sync_start(SCRIPT_NAME, hours=args.hours, factory=args.factory, dry_run=args.dry_run)

    # 加载配置
    logger.info("加载厂区配置: %s", args.config)
    factories = load_config(args.config)
    logger.info("共 %d 个厂区", len(factories))

    if args.factory:
        factories = [f for f in factories if f["factory_id"] == args.factory]
        if not factories:
            logger.error("❌ 未找到厂区: %s", args.factory)
            sys.exit(1)
        logger.info("筛选后: %d 个厂区", len(factories))

    # 连接 MongoDB
    if not args.dry_run:
        logger.info("连接 MongoDB: %s/%s", args.mongodb_uri, args.mongodb_db)
        mongo = MongoClient(args.mongodb_uri)
        db = mongo[args.mongodb_db]
        # 验证连接
        db.command("ping")
        logger.info("✅ MongoDB 连接成功")
    else:
        mongo = None
        db = None
        logger.info("⚠️  DRY RUN — 不写入数据")

    # 依次同步各厂区
    total_servers = 0
    total_details = 0
    total_skipped = 0
    failed_factories = []

    factory_bar = _progress(factories, desc="总体进度", unit="厂区")
    for factory in factory_bar:
        fid = factory["factory_id"]
        _write(f"\n{'='*60}")
        _write(f"📥 [{fid}] ── 开始同步 ──")
        factory_start = time.time()
        client = MESClient(factory, timeout=args.timeout)
        try:
            result = sync_factory(client, db, args.hours, dry_run=args.dry_run)
            total_servers += result["servers_total"]
            total_details += result["details_total"]
            total_skipped += result.get("skipped_servers", 0)

            if not args.dry_run:
                status = "success"
                save_job(db, status, fid, result)
                _write(f"[{fid}] ✅ 同步完成，已记录到 sync_jobs")
            else:
                _write(f"[{fid}] ⚠️  DRY RUN — 未写入实际数据")

            if tqdm is not None:
                factory_bar.set_postfix_str(
                    f"{result['servers_total']}台/{result['details_total']}条"
                )

        except Exception as e:
            failed_factories.append(fid)
            elapsed_factory = time.time() - factory_start
            logger.error(f"❌ [{fid}] 同步失败: {e} (耗时: {elapsed_factory:.1f}s)")
            log_sync_error(f"{SCRIPT_NAME}.{fid}", str(e), duration_ms=elapsed_factory * 1000)
            if not args.dry_run:
                save_job(db, "failed", fid, {
                    "servers_total": 0, "servers_new": 0,
                    "details_total": 0, "details_new": 0,
                }, str(e))
        finally:
            client.close()

    elapsed = time.time() - start_time
    _write("\n" + "=" * 60)
    _write("📊 同步汇总")
    _write(f"  厂区: {len(factories)} 个")
    _write(f"  服务器: {total_servers} 台")
    _write(f"  测试详情: {total_details} 条")
    if total_skipped:
        _write(f"  跳过: {total_skipped} 台")
    if failed_factories:
        _write(f"  失败: {', '.join(failed_factories)}")
    _write(f"  总耗时: {elapsed:.1f} 秒")

    logger.info("✅ 全部完成! 耗时: %.1f 秒", elapsed)
    log_sync_complete(SCRIPT_NAME, elapsed * 1000,
                      factories=len(factories), servers=total_servers,
                      details=total_details, skipped=total_skipped,
                      failed=len(failed_factories))

    if mongo:
        mongo.close()
        logger.info("MongoDB 连接已关闭")


if __name__ == "__main__":
    main()

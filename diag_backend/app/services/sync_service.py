"""
数据同步服务 - 从三方系统拉取数据并同步到 MongoDB
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

import requests

from ..core.config import get_settings
from ..core.mongodb import get_collection

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyncService:
    """数据同步服务"""

    def __init__(self):
        self.settings = get_settings()
        self._is_running = False
        self.servers_count = 0
        self.details_count = 0
        self._base_url = self.settings.sync_api_base_url
        self._headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self._base_url,
            "Referer": f"{self._base_url}/page/monitor_list.html",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }
        self._cookies = {"rolePower": ""}

    @property
    def is_running(self) -> bool:
        return self._is_running

    def _post(self, path: str, data: dict) -> dict:
        """发送 POST 请求（同步，在线程池中运行以避免阻塞事件循环）"""
        body = urlencode({k: v for k, v in data.items() if v is not None})
        full_url = f"{self._base_url}{path}"
        print(f"[HTTP] POST {full_url}")
        print(f"[HTTP] Body: {body[:200]}")
        try:
            resp = requests.post(
                full_url, data=body,
                headers=self._headers, cookies=self._cookies,
                timeout=self.settings.sync_api_timeout
            )
            print(f"[HTTP] Status: {resp.status_code}")
            print(f"[HTTP] Body[:500]: {resp.text[:500]}")
            resp.raise_for_status()
            result = resp.json()
            data_len = len(result.get("data", [])) if isinstance(result, dict) else 0
            total = result.get("total", "?")
            print(f"[HTTP] OK | {data_len} records, total={total}")
            return result
        except Exception as e:
            print(f"[HTTP] FAILED: {type(e).__name__}: {e}")
            raise

    async def _post_async(self, path: str, data: dict) -> dict:
        """异步包装 _post，在线程池中执行同步 requests 调用"""
        return await asyncio.to_thread(self._post, path, data)

    async def sync_all(self, full: bool = False) -> dict:
        """执行全量/增量同步"""
        if self._is_running:
            return {"message": "同步任务已在运行中"}

        self._is_running = True
        self.servers_count = 0
        self.details_count = 0
        servers_total = 0
        servers_new = 0
        details_total = 0
        details_new = 0
        skipped_servers = 0

        try:
            # Step 1: 拉取服务器列表（分页，始终全量 — 数据量小）
            logger.info("开始同步服务器列表...")
            all_servers = []
            page = 1
            limit = 100

            while True:
                resp = await self._post_async(
                    "/stepsmanagement/monitor/queryTestingServers.action",
                    data={"page": page, "limit": limit, "customerID": "", "salesReceipts": "", "orderID": "",
                          "serverSN": "", "serverState": "", "models": "", "productModels": "", "testItemName": ""}
                )
                batch = resp.get("data", [])
                all_servers.extend(batch)
                servers_total = resp.get("total", 0) or resp.get("count", 0)
                logger.info(f"Servers page {page}: {len(batch)} records")
                if len(batch) < limit:
                    break
                page += 1

            logger.info(f"Fetched {len(all_servers)} servers total")

            # 增量模式：读取已有 last_test_time（upsert 前读，避免被覆盖后丢失）
            servers_col = get_collection("sync_remote_servers")
            existing_times: dict[str, str] = {}
            if not full:
                cursor = servers_col.find(
                    {"server_sn": {"$in": [s.get("serverSN", "") for s in all_servers]}},
                    {"server_sn": 1, "last_test_time": 1}
                )
                async for doc in cursor:
                    t = doc.get("last_test_time")
                    if t:
                        existing_times[doc["server_sn"]] = t
                logger.info(f"Incremental mode: {len(existing_times)} servers have prior sync data")

            # Upsert 服务器（$set 不含 last_test_time，不会覆盖已有值）
            sn_to_id: dict[str, str] = {}

            for raw in all_servers:
                record = self._to_server_record(raw)
                result = await servers_col.update_one(
                    {"server_sn": record["server_sn"]},
                    {"$set": record},
                    upsert=True
                )
                if result.upserted_id:
                    servers_new += 1
                    sn_to_id[record["server_sn"]] = str(result.upserted_id)
                else:
                    existing = await servers_col.find_one({"server_sn": record["server_sn"]})
                    if existing:
                        sn_to_id[record["server_sn"]] = str(existing["_id"])

            self.servers_count = len(sn_to_id)
            logger.info(f"Servers synced: {len(sn_to_id)} total, {servers_new} new")

            # Step 2: 拉取每台服务器的测试详情（增量时利用 last_test_time 早停）
            mode = "FULL" if full else "INCREMENTAL"
            logger.info(f"[{mode}] Fetching test details for {len(sn_to_id)} servers...")
            details_col = get_collection("sync_remote_test_details")

            for sn, sid in sn_to_id.items():
                try:
                    since = None if full else existing_times.get(sn)
                    details, new_max_time = await self._fetch_test_details(sn, since)
                    if since and not details:
                        skipped_servers += 1
                        continue

                    for detail in details:
                        record = self._to_detail_record(sid, sn, detail)
                        result = await details_col.update_one(
                            {
                                "server_id": sid,
                                "detailed_flow": record["detailed_flow"],
                                "test_time": record["test_time"]
                            },
                            {"$set": record},
                            upsert=True
                        )
                        details_total += 1
                        if result.upserted_id:
                            details_new += 1

                    self.details_count += len(details)

                    # 更新 last_test_time
                    if new_max_time:
                        await servers_col.update_one(
                            {"server_sn": sn},
                            {"$set": {"last_test_time": new_max_time}}
                        )

                    logger.info(f"  {sn}: {len(details)} details" + (f" (since={since[:19]})" if since else ""))
                except Exception as e:
                    logger.error(f"Failed to sync details for {sn}: {e}")

            logger.info(f"[{mode}] Sync complete: {servers_total} servers, {details_total} details ({details_new} new)"
                        + (f", {skipped_servers} servers skipped" if skipped_servers else ""))
            await self._save_job("success", servers_total, servers_new, details_total, details_new, "")
            return {
                "message": "同步成功",
                "mode": "full" if full else "incremental",
                "servers_total": servers_total,
                "servers_new": servers_new,
                "details_total": details_total,
                "details_new": details_new,
                "skipped_servers": skipped_servers,
            }

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            await self._save_job("failed", servers_total, servers_new, details_total, details_new, str(e))
            raise
        finally:
            self._is_running = False

    async def _fetch_test_details(self, server_sn: str, since: Optional[str] = None) -> tuple[list[dict], Optional[str]]:
        """获取某服务器的测试详情，返回 (新记录列表, 最新test_time)。
        若 since 不为空，遇到 test_time <= since 的记录即停止（假设 API 按 test_time 倒序返回）。
        """
        all_data = []
        start = 0
        limit = 500
        max_time: Optional[str] = None

        while True:
            resp = await self._post_async(
                "/stepsmanagement/resultInfo/queryTestList.action",
                data={"start": start, "limit": limit, "serverSN": server_sn, "customerID": ""}
            )
            batch = resp.get("data", [])
            if not batch:
                break

            # 跟踪最大 test_time
            for d in batch:
                t = d.get("testTime")
                if t and (max_time is None or t > max_time):
                    max_time = t

            if since:
                new_batch = [d for d in batch if (d.get("testTime") or "") > since]
                all_data.extend(new_batch)
                # 如果过滤后数量少于原始批次，说明已越过水位线，停止翻页
                if len(new_batch) < len(batch):
                    break
            else:
                all_data.extend(batch)

            if len(batch) < limit:
                break
            start += limit

        return all_data, max_time

    async def _save_job(self, status: str, servers_total: int, servers_new: int,
                        details_total: int, details_new: int, error_message: str):
        col = get_collection("sync_jobs")
        await col.insert_one({
            "status": status,
            "started_at": _now_iso(),
            "servers_total": servers_total,
            "servers_new": servers_new,
            "details_total": details_total,
            "details_new": details_new,
            "error_message": error_message,
        })

    async def get_jobs(self, page: int = 1, limit: int = 5) -> dict:
        col = get_collection("sync_jobs")
        total = await col.count_documents({})
        skip = (page - 1) * limit
        cursor = col.find({}).sort("started_at", -1).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)
        for item in items:
            item["id"] = str(item.pop("_id"))
        return {"items": items, "total": total, "page": page, "limit": limit}

    def _to_server_record(self, raw: dict) -> dict:
        def _str(v, default=""):
            if v is None:
                return default
            if isinstance(v, (dict, list)):
                return str(v)
            return str(v)

        return {
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
            "item_begin_time": self._parse_datetime(raw.get("itemBeginTime")),
            "customer_id": _str(raw.get("customerID")),
            "customer_name": _str(raw.get("customerName")),
            "sales_receipts": _str(raw.get("salesReceipts")),
            "promised_date": _str(raw.get("promisedDate")),
            "maintenance_status": _str(raw.get("maintenanceStatus")),
            "final_operation": _str(raw.get("finalOperation")),
            "customized_system": _str(raw.get("customizedSystem")),
            "synced_at": _now_iso()
        }

    def _to_detail_record(self, server_id: str, server_sn: str, raw: dict) -> dict:
        return {
            "server_id": server_id,
            "server_sn": server_sn,
            "big_flow": raw.get("bigFlow", ""),
            "detailed_flow": raw.get("detailedFlow", ""),
            "log_path": raw.get("log", ""),
            "decision": raw.get("decision", ""),
            "server_test_result": raw.get("serverTestResult", ""),
            "test_time": self._parse_datetime(raw.get("testTime")),
            "mes_record": raw.get("mesRecord", ""),
            "fault_type1": raw.get("faultType1", ""),
            "fault_type2": raw.get("faultType2", ""),
            "fault_type3": raw.get("faultType3", ""),
            "mes_remarks": raw.get("mesRemarks", ""),
            "mes_time": self._parse_datetime(raw.get("mesTime")),
            "synced_at": _now_iso()
        }

    @staticmethod
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

    # ── 查询方法 ──

    async def get_servers(
        self,
        search_sn: Optional[str] = None,
        search_product_models: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        col = get_collection("sync_remote_servers")
        query = {}
        if search_sn:
            query["server_sn"] = {"$regex": search_sn, "$options": "i"}
        if search_product_models:
            query["product_models"] = {"$regex": search_product_models, "$options": "i"}

        total = await col.count_documents(query)
        skip = (page - 1) * limit
        cursor = col.find(query).sort("synced_at", -1).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)

        for item in items:
            item["id"] = str(item.pop("_id"))

        return {"items": items, "total": total, "page": page, "limit": limit}

    async def get_test_details(self, server_sn: str, page: int = 1, limit: int = 20) -> dict:
        col = get_collection("sync_remote_test_details")
        query = {"server_sn": server_sn}
        total = await col.count_documents(query)
        skip = (page - 1) * limit
        cursor = col.find(query).sort("test_time", -1).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)

        for item in items:
            item["id"] = str(item.pop("_id"))

        return {"items": items, "total": total, "page": page, "limit": limit}


_sync_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service

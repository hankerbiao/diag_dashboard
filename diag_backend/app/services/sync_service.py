"""
数据同步服务 - 从三方系统拉取数据并同步到 MongoDB
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

from bson import ObjectId

from ..core.config import get_settings
from ..core.mongodb import get_collection

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyncService:
    """数据同步服务"""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[httpx.AsyncClient] = None
        self._sync_lock = asyncio.Lock()
        self._sync_timeout: int = 3600

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.sync_api_base_url,
                timeout=httpx.Timeout(self.settings.sync_api_timeout),
                follow_redirects=True
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _post(self, url: str, data: dict) -> dict:
        """发送 POST 请求，带指数退避重试"""
        for attempt in range(self.settings.sync_max_retries):
            try:
                resp = await self.client.post(url, data=data)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error on attempt {attempt + 1}: {e}")
                if attempt == self.settings.sync_max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
            except httpx.TimeoutException as e:
                logger.warning(f"Timeout on attempt {attempt + 1}: {e}")
                if attempt == self.settings.sync_max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Request failed: {e}")
                raise

    async def _get_running_job(self) -> Optional[dict]:
        """获取当前运行中的同步任务"""
        col = get_collection("sync_jobs")
        return await col.find_one({"status": "running"})

    async def _create_job(self) -> str:
        """创建同步任务记录"""
        col = get_collection("sync_jobs")
        result = await col.insert_one({
            "status": "running",
            "started_at": _now_iso(),
            "finished_at": None,
            "servers_total": 0,
            "servers_new": 0,
            "details_total": 0,
            "details_new": 0,
            "error_message": ""
        })
        return str(result.inserted_id)

    async def _update_job(self, job_id: str, **fields):
        """更新同步任务"""
        col = get_collection("sync_jobs")
        fields["finished_at"] = _now_iso()
        await col.update_one({"_id": ObjectId(job_id)}, {"$set": fields})

    async def fetch_servers(self, page: int = 1, limit: int = 100) -> tuple[list[dict], int]:
        """获取服务器列表"""
        resp = await self._post(
            "/stepsmanagement/monitor/queryTestingServers.action",
            data={
                "page": page,
                "limit": limit,
                "customerID": "",
                "salesReceipts": "",
                "orderID": ""
            }
        )
        data = resp.get("data", [])
        total = resp.get("total", 0) or resp.get("count", 0)
        return data, total

    async def fetch_test_details(self, server_sn: str) -> list[dict]:
        """获取某服务器的测试详情（全量拉取）"""
        all_data = []
        start = 0
        limit = 500

        while True:
            resp = await self._post(
                "/stepsmanagement/resultInfo/queryTestList.action",
                data={
                    "start": start,
                    "limit": limit,
                    "serverSN": server_sn,
                    "customerID": ""
                }
            )
            batch = resp.get("data", [])
            all_data.extend(batch)
            if len(batch) < limit:
                break
            start += limit

        return all_data

    def _parse_datetime(self, value: Optional[str]) -> Optional[str]:
        """解析日期时间字符串，返回 ISO 格式字符串"""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").isoformat()
            except ValueError:
                return None

    def _to_server_record(self, raw: dict) -> dict:
        """将 API 返回的服务器数据转为数据库记录"""
        def _str(v, default=""):
            if v is None:
                return default
            if isinstance(v, (dict, list)):
                return str(v)
            return str(v)

        def _int(v, default=0):
            try:
                return int(v or default)
            except (ValueError, TypeError):
                return default

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
            "alarm": _int(raw.get("alarm")),
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

    def _to_detail_records(self, server_id: str, server_sn: str, raw_list: list[dict]) -> list[dict]:
        """将 API 返回的测试详情数据转为数据库记录"""
        records = []
        for raw in raw_list:
            records.append({
                "server_id": server_id,
                "server_sn": server_sn,
                "big_flow": raw.get("bigFlow", ""),
                "detailed_flow": raw.get("detailedFlow", ""),
                "log_path": raw.get("logPath", ""),
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
            })
        return records

    async def sync_all(self, triggered_by: str = "manual") -> dict:
        """执行全量同步（带整体超时保护）"""
        if self._sync_lock.locked():
            running = await self._get_running_job()
            if running:
                return {"job_id": str(running["_id"]), "message": "同步任务已在运行中"}

        try:
            return await asyncio.wait_for(self._do_sync(), timeout=self._sync_timeout)
        except asyncio.TimeoutError:
            logger.error("同步任务超时")
            return {"job_id": "", "message": "同步任务超时"}
        except Exception:
            logger.exception("同步任务失败")
            raise

    async def _do_sync(self) -> dict:
        """同步内部实现"""
        async with self._sync_lock:
            job_id = await self._create_job()
            servers_total = 0
            servers_new = 0
            details_total = 0
            details_new = 0
            errors = []

            try:
                # Step 1: 拉取服务器列表（分页）
                logger.info("开始同步服务器列表...")
                all_servers = []
                page = 1
                limit = 100

                while True:
                    data, total = await self.fetch_servers(page, limit)
                    all_servers.extend(data)
                    servers_total = total
                    if len(data) < limit:
                        break
                    page += 1

                # Upsert 服务器数据
                servers_col = get_collection("sync_remote_servers")
                sn_to_id: dict[str, str] = {}

                for s in all_servers:
                    record = self._to_server_record(s)
                    result = await servers_col.update_one(
                        {"server_sn": record["server_sn"]},
                        {"$set": record},
                        upsert=True
                    )
                    if result.upserted_id:
                        servers_new += 1
                        sn_to_id[record["server_sn"]] = str(result.upserted_id)
                    else:
                        # 获取已有记录 ID
                        existing = await servers_col.find_one({"server_sn": record["server_sn"]})
                        if existing:
                            sn_to_id[record["server_sn"]] = str(existing["_id"])

                logger.info(f"同步了 {len(sn_to_id)} 台服务器")

                # Step 2: 并发拉取每台服务器的测试详情
                semaphore = asyncio.Semaphore(self.settings.sync_max_concurrency)
                details_col = get_collection("sync_remote_test_details")

                async def sync_one_server(sn: str, sid: str):
                    async with semaphore:
                        try:
                            details = await self.fetch_test_details(sn)
                            new_count = 0
                            if details:
                                for detail in details:
                                    record = self._to_detail_records(sid, sn, [detail])[0]
                                    result = await details_col.update_one(
                                        {
                                            "server_id": sid,
                                            "detailed_flow": record["detailed_flow"],
                                            "test_time": record["test_time"]
                                        },
                                        {"$set": record},
                                        upsert=True
                                    )
                                    if result.upserted_id:
                                        new_count += 1
                            return len(details), new_count
                        except Exception as e:
                            logger.error(f"同步服务器 {sn} 测试详情失败: {e}")
                            errors.append(f"{sn}: {str(e)}")
                            return 0, 0

                tasks = [sync_one_server(sn, sid) for sn, sid in sn_to_id.items()]
                results = await asyncio.gather(*tasks)

                for r in results:
                    details_total += r[0]
                    details_new += r[1]

                # 更新任务状态为成功
                error_msg = "; ".join(errors) if errors else ""
                await self._update_job(
                    job_id,
                    status="success",
                    servers_total=servers_total,
                    servers_new=servers_new,
                    details_total=details_total,
                    details_new=details_new,
                    error_message=error_msg
                )

                logger.info(f"同步完成: {servers_total} 台服务器, {details_total} 条测试详情")
                return {"job_id": job_id, "message": "同步成功"}

            except Exception as e:
                logger.error(f"同步失败: {e}")
                error_msg = str(e)
                if errors:
                    error_msg += "; 另有错误: " + "; ".join(errors)
                await self._update_job(
                    job_id,
                    status="failed",
                    servers_total=servers_total,
                    servers_new=servers_new,
                    details_total=details_total,
                    details_new=details_new,
                    error_message=error_msg
                )
                raise

    async def get_servers(
        self,
        search_sn: Optional[str] = None,
        search_product_models: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        """查询服务器列表"""
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

        # 转换 ObjectId 为字符串
        for item in items:
            item["id"] = str(item.pop("_id"))

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    async def get_test_details(self, server_sn: str, page: int = 1, limit: int = 20) -> dict:
        """查询某服务器的测试详情"""
        col = get_collection("sync_remote_test_details")
        query = {"server_sn": server_sn}
        total = await col.count_documents(query)
        skip = (page - 1) * limit

        cursor = col.find(query).sort("test_time", -1).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)

        for item in items:
            item["id"] = str(item.pop("_id"))

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    async def get_jobs(self, page: int = 1, limit: int = 20) -> dict:
        """查询同步历史"""
        col = get_collection("sync_jobs")
        total = await col.count_documents({})
        skip = (page - 1) * limit

        cursor = col.find({}).sort("started_at", -1).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)

        for item in items:
            item["id"] = str(item.pop("_id"))

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    async def get_latest_job_status(self) -> Optional[dict]:
        """获取最新同步状态"""
        col = get_collection("sync_jobs")
        item = await col.find_one({}, sort=[("started_at", -1)])
        if item:
            item["id"] = str(item.pop("_id"))
        return item


# 单例
_sync_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service
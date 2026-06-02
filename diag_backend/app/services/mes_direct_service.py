"""
MES API 实时查询服务 - 直连各厂区 MES 获取实时数据（无缓存、无降级）

与 scripts/sync_data.py 的 MESClient 逻辑一致，但：
1. 使用 httpx.AsyncClient（异步）
2. 不写入 MongoDB，只返回数据
3. 无降级策略，MES 出错直接 raise
"""
import asyncio
import json
import logging
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from ..core.factory_config import get_factory_by_id
from ..core.config import get_settings
from ..core.utils import utc_now_iso

logger = logging.getLogger(__name__)

# 并发控制：限制同时发出的 MES API 请求数
_MES_SEMAPHORE = asyncio.Semaphore(3)


class MESRequestError(Exception):
    """MES HTTP 请求失败，附带可排查的请求上下文。"""

    def __init__(self, message: str, *, debug: dict[str, Any]):
        super().__init__(message)
        self.debug = debug


class ServerInfo(BaseModel):
    """服务器信息（与 SyncService 返回格式一致）"""
    id: str = ""
    factory_id: str = ""
    server_sn: str = ""
    model: str = ""
    product_models: str = ""
    customer: str = ""
    order_id: str = ""
    server_state: str = ""
    synced_at: str = ""


class MESDirectService:
    """直连各厂区 MES API 的实时查询服务（无缓存、无降级）

    支持 async context manager 自动清理连接：
        async with MESDirectService() as mes:
            result = await mes.search_servers(...)
    """

    def __init__(self):
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._timeout = get_settings().mes_request_timeout

    async def __aenter__(self) -> "MESDirectService":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    def _get_client(self, factory_id: str) -> httpx.AsyncClient:
        """获取或创建指定厂区的 HTTP 客户端（连接池复用）"""
        if factory_id not in self._clients:
            factory = get_factory_by_id(factory_id)
            if not factory:
                raise ValueError(f"厂区不存在: {factory_id}")
            base_url = factory["base_url"].rstrip("/")
            # 与 scripts/sync_data.py MESClient 一致：桐乡等厂区 MES 会校验 Origin/Referer，缺失时返回 403
            self._clients[factory_id] = httpx.AsyncClient(
                base_url=base_url,
                timeout=self._timeout,
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": base_url,
                    "Referer": f"{base_url}/page/monitor_list.html",
                },
            )
        return self._clients[factory_id]

    def _request_debug(self, factory_id: str, path: str, data: dict) -> dict[str, Any]:
        """组装 MES 请求调试信息（URL + 入参）。"""
        factory = get_factory_by_id(factory_id) or {}
        base_url = (factory.get("base_url") or "").rstrip("/")
        params = {k: v for k, v in data.items() if v is not None}
        return {
            "factory_id": factory_id,
            "factory_name": factory.get("name", ""),
            "base_url": base_url,
            "path": path,
            "method": "POST",
            "url": f"{base_url}{path}" if base_url else path,
            "params": params,
            "body": urlencode(params),
        }

    def _log_request_failure(self, debug: dict[str, Any], error: Exception, response: Any = None) -> None:
        """失败时打印请求地址与入参，便于排查 SIMS/MES 连通性问题。"""
        payload = {**debug, "error": str(error), "error_type": type(error).__name__}
        if response is not None:
            payload["status_code"] = getattr(response, "status_code", None)
            text = getattr(response, "text", "") or ""
            if text:
                payload["response_preview"] = text[:800]
        logger.warning(
            "MES API 请求失败 factory=%s url=%s error=%s",
            debug.get("factory_id"),
            debug.get("url"),
            error,
        )
        logger.debug("MES API 请求详情: %s", json.dumps(payload, ensure_ascii=False, default=str))

    async def _post(self, factory_id: str, path: str, data: dict) -> dict:
        """POST 请求封装（受 Semaphore 并发控制）"""
        debug = self._request_debug(factory_id, path, data)
        async with _MES_SEMAPHORE:
            client = self._get_client(factory_id)
            body = debug["body"]
            try:
                resp = await client.post(path, data=body)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                self._log_request_failure(debug, e, e.response)
                raise MESRequestError(str(e), debug=debug) from e
            except httpx.RequestError as e:
                self._log_request_failure(debug, e)
                raise MESRequestError(str(e), debug=debug) from e
            except Exception as e:
                self._log_request_failure(debug, e)
                raise MESRequestError(str(e), debug=debug) from e

    async def search_servers(
        self,
        factory_id: str,
        *,
        sn: str = "",
        product_models: str = "",
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """搜索服务器列表 → 直连 MES API"""
        resp = await self._post(
            factory_id,
            "/stepsmanagement/monitor/queryTestingServers.action",
            {
                "page": page, "limit": limit,
                "serverSN": sn, "productModels": product_models,
                "customerID": "", "salesReceipts": "", "orderID": "",
                "serverState": "", "models": "", "testItemName": "",
            },
        )
        items = resp.get("data", [])
        total = resp.get("total", len(items))
        return self._normalize_servers(factory_id, items, total, page, limit)

    async def get_server(self, factory_id: str, server_sn: str) -> Optional[ServerInfo]:
        """精确查询单个服务器"""
        resp = await self._post(
            factory_id,
            "/stepsmanagement/monitor/queryTestingServers.action",
            {
                "page": 1, "limit": 1,
                "serverSN": server_sn, "productModels": "",
                "customerID": "", "salesReceipts": "", "orderID": "",
                "serverState": "", "models": "", "testItemName": "",
            },
        )
        items = resp.get("data", [])
        if items:
            return self._normalize_server(factory_id, items[0])
        return None

    async def get_test_details(
        self,
        factory_id: str,
        server_sn: str,
        offset: int = 0,
        limit: int = 500,
    ) -> dict:
        """查询测试明细 → 直连 MES API

        返回 {"items": [...], "total": int}。
        MES API 使用 start/limit 分页，返回的 total 为真实总数。
        """
        resp = await self._post(
            factory_id,
            "/stepsmanagement/resultInfo/queryTestList.action",
            {
                "start": offset, "limit": min(limit, 500),
                "serverSN": server_sn, "customerID": "",
            },
        )
        batch = resp.get("data", [])
        total = resp.get("total", len(batch))
        items = self._normalize_test_details(batch, factory_id)
        return {"items": items, "total": total}

    def _normalize_servers(
        self,
        factory_id: str,
        raw: list[dict],
        total: int,
        page: int,
        limit: int,
    ) -> dict:
        """字段映射，与 SyncService 返回格式一致"""
        now = utc_now_iso()
        items = []
        for r in raw:
            sn = r.get("serverSN", "")
            items.append({
                "id": f"{factory_id}_{sn}" if sn else "",
                "factory_id": factory_id,
                "server_sn": sn,
                "order_id": r.get("orderID", ""),
                "model": r.get("model", ""),
                "product_models": r.get("productModels", ""),
                "host_ip": r.get("hostIP", ""),
                "server_state": r.get("serverState", ""),
                "test_items": r.get("testItems", ""),
                "next_item": r.get("nextItem", ""),
                "position": r.get("position", ""),
                "customer_name": r.get("customerName", ""),
                "alarm": int(r.get("alarm") or 0),
                "synced_at": now,
            })
        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
        }

    def _normalize_server(self, factory_id: str, raw: dict) -> ServerInfo:
        """单个服务器字段映射"""
        return ServerInfo(
            id="",
            factory_id=factory_id,
            server_sn=raw.get("serverSN", ""),
            model=raw.get("model", ""),
            product_models=raw.get("productModels", ""),
            customer=raw.get("customer", ""),
            order_id=raw.get("orderID", ""),
            server_state=raw.get("serverState", ""),
            synced_at=utc_now_iso(),
        )

    def _normalize_test_details(
        self, batch: list[dict], factory_id: str
    ) -> list[dict]:
        """测试明细字段映射，与 MongoDB sync_remote_test_details 格式一致"""
        normalized = []
        for idx, r in enumerate(batch):
            sn = r.get("serverSN", "")
            test_time = r.get("testTime", "")
            normalized.append({
                "id": f"{factory_id}_{sn}_{test_time}_{idx}",
                "factory_id": factory_id,
                "server_sn": sn,
                "test_time": test_time,
                "detailed_flow": r.get("detailedFlow", ""),
                "big_flow": r.get("bigFlow", ""),
                "server_test_result": r.get("serverTestResult", ""),
                "fault_type1": r.get("faultType1", ""),
                "fault_type2": r.get("faultType2", ""),
                "fault_type3": r.get("faultType3", ""),
                "decision": r.get("decision", ""),
                "log_path": r.get("log", ""),
                "mes_record": r.get("mesRecord", ""),
                "customer_id": r.get("customerID", ""),
            })
        return normalized

    async def close(self):
        """关闭所有连接"""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

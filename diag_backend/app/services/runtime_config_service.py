"""
RuntimeConfigService — 进程级运行时性能配置（内存缓存 + generation 版本号 + TTL）。

存储于 MongoDB.global_app_config 文档 _id="runtime_config"，由设置页 API 读写，
管理日志提取并发等性能参数：

- get()：懒加载 + TTL 兜底刷新；DB 不可达时快速回退默认值，永不抛异常；
- apply_update()：写库成功后立即刷新本进程内存缓存并递增 generation，
  同步调整全局动态信号量容量 → 单进程部署下实时生效；
  多进程部署时其余进程在 TTL 过期后自动重读对齐；
- cached()：纯内存只读，供信号量创建等同步路径使用。

依赖方向：runtime_config_service 不在顶层导入 log_processing，
避免与 log_processing 包形成循环依赖（对 ai_extractor 的调用均在函数内延迟导入）。
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

DOC_ID = "runtime_config"

DEFAULTS: dict[str, int] = {
    "per_request_concurrency": 8,  # 单请求内并发提取段数
    "global_concurrency": 16,      # 进程级全局并发提取上限
}

_TTL_SECONDS = 60.0


class RuntimeConfigService:
    def __init__(self, ttl: float = _TTL_SECONDS):
        self._config: dict[str, int] = dict(DEFAULTS)
        self._loaded_at = 0.0
        self._ttl = max(1.0, ttl)
        self._initialized = False
        self.generation = 0  # 版本号：配置每次变更 +1，供前端/信号量感知变更

    def cached(self) -> dict[str, int]:
        """纯内存只读（不触发 DB），用于同步路径。"""
        return dict(self._config)

    async def get(self) -> dict[str, int]:
        """返回当前生效配置；缓存未过期时零 DB 开销。永不抛异常。"""
        if self._initialized and time.monotonic() - self._loaded_at < self._ttl:
            return dict(self._config)
        try:
            await self._reload_from_db()
        except Exception as exc:  # noqa: BLE001
            logger.warning("运行时配置加载失败，使用默认值: %s", exc)
            if not self._initialized:
                self._config = dict(DEFAULTS)
                self._initialized = True
        return dict(self._config)

    async def _reload_from_db(self) -> None:
        from ..core.mongodb import get_collection

        col = get_collection("global_app_config")
        doc = await col.find_one({"_id": DOC_ID})
        self._config = self._merge(doc)
        self._loaded_at = time.monotonic()
        self._initialized = True
        self.generation += 1
        # 全局信号量容量对齐（多进程 TTL 刷新路径；单值未变时 set_limit 为 no-op）
        self._sync_global_semaphore()

    def _merge(self, doc: dict | None) -> dict[str, int]:
        cfg = dict(DEFAULTS)
        if not doc:
            return cfg
        raw = doc.get("log_extraction") or {}
        for key in DEFAULTS:
            value = raw.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                cfg[key] = max(1, value)
        return cfg

    async def apply_update(self, values: dict[str, int]) -> dict[str, int]:
        """写库 + 刷新内存缓存 + 递增版本号，并同步全局信号量容量（实时生效）。"""
        from ..core.mongodb import get_collection
        from ..core.utils import utc_now_iso

        col = get_collection("global_app_config")
        update_data = {f"log_extraction.{key}": int(values[key]) for key in values}
        update_data["updated_at"] = utc_now_iso()
        await col.update_one({"_id": DOC_ID}, {"$set": update_data}, upsert=True)

        self._config.update(values)
        self._loaded_at = time.monotonic()
        self._initialized = True
        self.generation += 1
        if "global_concurrency" in values:
            self._sync_global_semaphore()
        return dict(self._config)

    def _sync_global_semaphore(self) -> None:
        """将全局并发上限同步到 AI 提取器（延迟导入避免循环依赖）。"""
        try:
            from .log_processing.ai_extractor import set_global_concurrency

            set_global_concurrency(int(self._config.get("global_concurrency", DEFAULTS["global_concurrency"])))
        except Exception as exc:  # noqa: BLE001
            logger.debug("同步全局并发信号量失败: %s", exc)


runtime_config_service = RuntimeConfigService()

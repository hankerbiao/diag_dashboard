"""
自动数据同步调度服务

每 60 秒轮询 auto_sync_configs 集合，到期则启动对应的同步脚本 subprocess。
SIMS: 各厂区独立间隔（默认 60 分钟），调用 sync_data.py
MES:  全局单条配置（默认 1440 分钟），调用 sync_mes.py
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from bson import ObjectId

from ..core.mongodb import get_collection

logger = logging.getLogger(__name__)

_SCRIPTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
)

# Sentinel key for MES global config (never matches a real factory_id)
MES_CONFIG_KEY = "__mes__"


async def execute_sync_script(cmd: List[str], job_id: str) -> str:
    """运行同步脚本子进程，逐行读取输出并实时更新 job 进度。

    Args:
        cmd: 命令行参数列表
        job_id: sync_jobs 集合中的任务 _id (字符串)

    Returns:
        最终状态: "completed" 或 "failed"
    """
    col = get_collection("sync_jobs")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    output_lines: List[str] = []
    loop = asyncio.get_running_loop()
    last_flush = loop.time()

    async def _read_stream(stream: asyncio.StreamReader, label: str):
        nonlocal last_flush
        async for line in stream:
            text = line.decode(errors="replace")
            output_lines.append(f"[{label}] {text}")
            now = loop.time()
            if now - last_flush >= 2:
                await col.update_one(
                    {"_id": ObjectId(job_id)},
                    {"$set": {"progress": "".join(output_lines[-30:])}},
                )
                last_flush = now

    # 并发读取 stdout 和 stderr
    _, stderr_data = await asyncio.gather(
        _read_stream(proc.stdout, "out"),
        proc.stderr.read(),  # stderr 一次性读完，量小
        return_exceptions=True,
    )

    await proc.wait()
    status = "completed" if proc.returncode == 0 else "failed"
    output = "".join(output_lines[-50:])
    stderr_text = stderr_data.decode(errors="replace")[-500:] if stderr_data else ""

    await col.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {
            "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": output,
            "output": output,
            "error": stderr_text,
        }},
    )
    logger.info("Sync job %s finished: %s", job_id, status)
    return status


def _parse_iso(val) -> Optional[datetime]:
    """将 ISO 字符串或 datetime 转为 UTC datetime，失败返回 None"""
    if not val:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
    try:
        dt = datetime.fromisoformat(str(val))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


class SyncSchedulerService:
    def __init__(self):
        self._sims_task: Optional[asyncio.Task] = None
        self._mes_task: Optional[asyncio.Task] = None
        self._scheduler_stop = asyncio.Event()
        self._running_jobs: Dict[str, asyncio.Task] = {}

    # ── Subprocess Execution ──

    async def _run_sims_sync(self, factory_id: str, cutoff_hours: int) -> dict:
        key = f"sims:{factory_id}"
        if self._running_jobs.get(key) and not self._running_jobs[key].done():
            return {"status": "skipped", "reason": f"厂区 {factory_id} 同步任务已在执行中"}

        col = get_collection("sync_jobs")
        result = await col.insert_one({
            "factory_id": factory_id, "sync_type": "sims", "status": "running",
            "triggered_by": "scheduler",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        job_id = str(result.inserted_id)
        cmd = ["python", f"{_SCRIPTS_DIR}/sync_data.py", "--factory", factory_id,
               "--hours", str(cutoff_hours or 24)]

        async def _execute():
            if await execute_sync_script(cmd, job_id) == "completed":
                await get_collection("auto_sync_configs").update_one(
                    {"factory_id": factory_id},
                    {"$set": {"last_run_at": datetime.now(timezone.utc)}},
                )

        self._running_jobs[key] = asyncio.create_task(_execute())
        return {"job_id": job_id, "status": "started"}

    async def _run_mes_sync(self) -> dict:
        key = "mes:global"
        if self._running_jobs.get(key) and not self._running_jobs[key].done():
            return {"status": "skipped", "reason": "MES 同步任务已在执行中"}

        col = get_collection("sync_jobs")
        result = await col.insert_one({
            "factory_id": MES_CONFIG_KEY, "sync_type": "mes", "status": "running",
            "triggered_by": "scheduler",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        job_id = str(result.inserted_id)
        cmd = ["python", f"{_SCRIPTS_DIR}/sync_mes.py", "--sync-recent", "1"]

        async def _execute():
            if await execute_sync_script(cmd, job_id) == "completed":
                await get_collection("auto_sync_configs").update_one(
                    {"factory_id": MES_CONFIG_KEY},
                    {"$set": {"last_run_at": datetime.now(timezone.utc)}},
                )

        self._running_jobs[key] = asyncio.create_task(_execute())
        return {"job_id": job_id, "status": "started"}

    # ── Scheduler Loops ──

    async def _sims_scheduler_loop(self):
        logger.info("SIMS auto-sync scheduler started")
        while not self._scheduler_stop.is_set():
            try:
                await asyncio.wait_for(self._scheduler_stop.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            if self._scheduler_stop.is_set():
                break

            try:
                configs = await self._load_sims_configs()
                now = datetime.now(timezone.utc)
                for cfg in configs:
                    if not cfg.get("enabled"):
                        continue
                    interval = cfg.get("interval_minutes", 60)
                    last_run = _parse_iso(cfg.get("last_run_at"))
                    if last_run is None or (now - last_run).total_seconds() >= interval * 60:
                        asyncio.create_task(self._run_sims_sync(
                            cfg["factory_id"],
                            cfg.get("cutoff_hours") or 24,
                        ))
            except Exception:
                logger.exception("SIMS scheduler poll failed")

    async def _mes_scheduler_loop(self):
        logger.info("MES auto-sync scheduler started")
        while not self._scheduler_stop.is_set():
            try:
                await asyncio.wait_for(self._scheduler_stop.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            if self._scheduler_stop.is_set():
                break

            try:
                cfg = await self._load_mes_config()
                if not cfg.get("enabled"):
                    continue
                interval = cfg.get("interval_minutes", 1440)
                now = datetime.now(timezone.utc)
                last_run = _parse_iso(cfg.get("last_run_at"))
                if last_run is None or (now - last_run).total_seconds() >= interval * 60:
                    asyncio.create_task(self._run_mes_sync())
            except Exception:
                logger.exception("MES scheduler poll failed")

    # ── Config Loaders ──

    async def _load_sims_configs(self) -> List[dict]:
        col = get_collection("auto_sync_configs")
        cursor = col.find({"factory_id": {"$ne": MES_CONFIG_KEY}}).sort("factory_id", 1)
        return await cursor.to_list(length=100)

    async def _load_mes_config(self) -> dict:
        col = get_collection("auto_sync_configs")
        cfg = await col.find_one({"factory_id": MES_CONFIG_KEY})
        return cfg or {"enabled": False, "interval_minutes": 1440, "last_run_at": None}

    # ── Public API: Config ──

    async def get_configs(self) -> dict:
        sims_configs = await self._load_sims_configs()
        mes_config = await self._load_mes_config()
        return {
            "sims": {
                "enabled": any(c.get("enabled") for c in sims_configs),
                "interval_minutes": 60,
                "factories": [
                    {
                        "factory_id": c["factory_id"],
                        "enabled": c.get("enabled", False),
                        "interval_minutes": c.get("interval_minutes", 60),
                        "cutoff_hours": c.get("cutoff_hours"),
                        "last_run_at": c.get("last_run_at"),
                    }
                    for c in sims_configs
                ],
            },
            "mes": {
                "enabled": mes_config.get("enabled", False),
                "interval_minutes": mes_config.get("interval_minutes", 1440),
                "cutoff_hours": mes_config.get("cutoff_hours"),
                "last_run_at": mes_config.get("last_run_at"),
            },
        }

    async def update_config(self, request) -> dict:
        col = get_collection("auto_sync_configs")
        now = datetime.now(timezone.utc)

        sims_enabled = getattr(request, "sims_enabled", None)
        sims_interval = getattr(request, "sims_interval_minutes", None)
        if sims_enabled is not None or sims_interval is not None:
            update = {"updated_at": now}
            if sims_enabled is not None:
                update["enabled"] = sims_enabled
            if sims_interval is not None:
                update["interval_minutes"] = sims_interval
            await col.update_many(
                {"factory_id": {"$ne": MES_CONFIG_KEY}},
                {"$set": update},
            )

        factory_overrides = getattr(request, "factory_overrides", None)
        if factory_overrides:
            for fid, override in factory_overrides.items():
                upd = {}
                if override.enabled is not None:
                    upd["enabled"] = override.enabled
                if override.interval_minutes is not None:
                    upd["interval_minutes"] = override.interval_minutes
                if override.cutoff_hours is not None:
                    upd["cutoff_hours"] = override.cutoff_hours
                if upd:
                    upd["updated_at"] = now
                    await col.update_one({"factory_id": fid}, {"$set": upd})

        mes_enabled = getattr(request, "mes_enabled", None)
        mes_interval = getattr(request, "mes_interval_minutes", None)
        if mes_enabled is not None or mes_interval is not None:
            mes_update = {"updated_at": now}
            if mes_enabled is not None:
                mes_update["enabled"] = mes_enabled
            if mes_interval is not None:
                mes_update["interval_minutes"] = mes_interval
            await col.update_one(
                {"factory_id": MES_CONFIG_KEY},
                {"$set": mes_update},
            )

        return await self.get_configs()

    # ── Public API: Manual Triggers ──

    async def trigger_sims_now(self, factory_id: Optional[str] = None) -> List[dict]:
        if factory_id:
            cfg = await get_collection("auto_sync_configs").find_one({"factory_id": factory_id})
            cutoff = cfg.get("cutoff_hours") if cfg else 24
            return [await self._run_sims_sync(factory_id, cutoff or 24)]
        configs = await self._load_sims_configs()
        results = []
        for cfg in configs:
            if cfg.get("enabled", False):
                r = await self._run_sims_sync(cfg["factory_id"], cfg.get("cutoff_hours") or 24)
                results.append(r)
        return results

    async def trigger_mes_now(self) -> dict:
        return await self._run_mes_sync()

    # ── Start / Stop ──

    def start_scheduler(self):
        self._scheduler_stop.clear()
        if self._sims_task is None or self._sims_task.done():
            self._sims_task = asyncio.create_task(self._sims_scheduler_loop())
        if self._mes_task is None or self._mes_task.done():
            self._mes_task = asyncio.create_task(self._mes_scheduler_loop())
        logger.info("Sync scheduler started (SIMS + MES)")

    async def stop_scheduler(self):
        self._scheduler_stop.set()
        for task in [self._sims_task, self._mes_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._sims_task = None
        self._mes_task = None
        logger.info("Sync scheduler stopped")


# ── Singleton ──

_sync_scheduler: Optional[SyncSchedulerService] = None


def get_sync_scheduler_service() -> SyncSchedulerService:
    global _sync_scheduler
    if _sync_scheduler is None:
        _sync_scheduler = SyncSchedulerService()
    return _sync_scheduler

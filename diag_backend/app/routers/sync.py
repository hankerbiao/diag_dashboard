"""
数据同步路由 - 查询已同步数据，触发同步
数据写入由独立脚本 (scripts/sync_data.py) 完成
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.auth import get_current_user, require_role
from ..core.mongodb import get_collection
from ..models.request import AutoSyncConfigUpdateRequest
from ..models.response import ApiResponse
from ..services.sync_service import get_sync_service
from ..services.sync_scheduler_service import get_sync_scheduler_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["数据同步"])

_sync_lock = asyncio.Lock()

_SCRIPTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
)


@router.post("/trigger", response_model=ApiResponse)
async def trigger_sync(
    factory: Optional[str] = Query(None, description="指定厂区，不传则全部同步"),
    current_user: dict = Depends(require_role(["admin", "engineer"])),
):
    """触发数据同步（调用 sync_data.py 脚本，需要 admin/engineer 角色）"""
    if _sync_lock.locked():
        return ApiResponse(success=False, error="已有同步任务正在进行中")

    async with _sync_lock:
        try:
            cmd = ["python", f"{_SCRIPTS_DIR}/sync_data.py"]
            if factory:
                cmd.extend(["--factory", factory])

            # 记录同步任务
            col = get_collection("sync_jobs")
            job = {
                "factory_id": factory or "all",
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "triggered_by": current_user.get("email", current_user["id"]),
            }
            result = await col.insert_one(job)
            job_id = str(result.inserted_id)

            # 异步执行同步（不阻塞响应）
            async def run_sync():
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                status = "completed" if proc.returncode == 0 else "failed"
                await col.update_one(
                    {"_id": result.inserted_id},
                    {"$set": {
                        "status": status,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "output": stdout.decode()[-1000:] if stdout else "",
                        "error": stderr.decode()[-1000:] if stderr else "",
                    }},
                )
                logger.info("Sync job %s finished with status: %s", job_id, status)

            asyncio.create_task(run_sync())

            return ApiResponse(
                success=True,
                data={"job_id": job_id, "status": "running"},
                message=f"同步任务已启动{f'（厂区: {factory}）' if factory else ''}",
            )

        except Exception as e:
            logger.error("Trigger sync failed: %s", e)
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers")
async def get_servers(
    factory_id: Optional[str] = Query(None, description="厂区标识，不传则查全部"),
    search_sn: Optional[str] = Query(None, description="服务器 SN 模糊搜索"),
    search_product_models: Optional[str] = Query(None, description="产品型号模糊搜索"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """查询服务器列表，可按厂区过滤"""
    svc = get_sync_service()
    result = await svc.get_servers(
        factory_id=factory_id,
        search_sn=search_sn,
        search_product_models=search_product_models,
        page=page,
        limit=limit
    )
    return ApiResponse(success=True, data=result)


@router.get("/servers/{server_sn}/test-details")
async def get_test_details(
    server_sn: str,
    factory_id: Optional[str] = Query(None, description="厂区标识，不传则查全部"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=500, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """查询某服务器的测试详情"""
    svc = get_sync_service()
    result = await svc.get_test_details(
        server_sn=server_sn,
        factory_id=factory_id,
        page=page,
        limit=limit
    )
    return ApiResponse(success=True, data=result)


@router.get("/jobs")
async def get_jobs(
    factory_id: Optional[str] = Query(None, description="厂区标识，不传则查全部"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(5, ge=1, le=20, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """查询同步历史记录"""
    svc = get_sync_service()
    result = await svc.get_jobs(factory_id=factory_id, page=page, limit=limit)
    return ApiResponse(success=True, data=result)


# ── 自动同步配置 ──


@router.get("/auto-config", response_model=ApiResponse)
async def get_auto_sync_config(current_user: dict = Depends(get_current_user)):
    """获取自动同步配置（SIMS + MES）"""
    svc = get_sync_scheduler_service()
    config = await svc.get_configs()
    return ApiResponse(success=True, data=config)


@router.put("/auto-config", response_model=ApiResponse)
async def update_auto_sync_config(
    request: AutoSyncConfigUpdateRequest,
    current_user: dict = Depends(require_role(["admin"])),
):
    """更新自动同步配置（仅 admin）"""
    svc = get_sync_scheduler_service()
    result = await svc.update_config(request)
    return ApiResponse(success=True, data=result, message="自动同步配置已更新")


@router.post("/trigger-mes", response_model=ApiResponse)
async def trigger_mes_sync(
    current_user: dict = Depends(require_role(["admin", "engineer"])),
):
    """手动触发 MES 维修数据同步"""
    svc = get_sync_scheduler_service()
    result = await svc.trigger_mes_now()
    return ApiResponse(success=True, data=result, message="MES 同步任务已启动")

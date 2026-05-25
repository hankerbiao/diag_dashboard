"""
数据同步路由
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from ..core.auth import get_current_user
from ..models.response import (
    ApiResponse,
    SyncServerResponse,
    SyncTestDetailResponse,
    SyncJobResponse,
    PaginatedResponse
)
from ..services.sync_service import get_sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["数据同步"])


async def _run_sync_background():
    """后台执行同步任务"""
    try:
        sync_service = get_sync_service()
        await sync_service.sync_all(triggered_by="manual")
        logger.info("后台同步任务完成")
    except Exception as e:
        logger.error(f"后台同步任务失败: {e}")


@router.post("/trigger")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    手动触发同步任务
    立即返回 job_id，后台执行同步
    """
    sync_service = get_sync_service()

    try:
        # 检查是否有正在运行的同步任务
        running_job = await sync_service.get_latest_job_status()
        if running_job and running_job.get("status") == "running":
            return ApiResponse(
                success=True,
                data={"job_id": running_job["id"]},
                message="同步任务已在运行中"
            )

        # 立即返回，后台执行同步
        background_tasks.add_task(_run_sync_background)

        # 获取当前最新的 job_id（如果已有）
        latest = await sync_service.get_latest_job_status()
        job_id = latest["id"] if latest else None

        return ApiResponse(
            success=True,
            data={"job_id": job_id or "pending"},
            message="同步任务已加入队列"
        )
    except Exception as e:
        logger.error(f"触发同步任务失败: {e}")
        return ApiResponse(
            success=False,
            error=str(e),
            message="同步任务启动失败"
        )


@router.get("/servers")
async def get_servers(
    search_sn: Optional[str] = Query(None, description="服务器 SN 模糊搜索"),
    search_product_models: Optional[str] = Query(None, description="产品型号模糊搜索"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """查询服务器列表"""
    sync_service = get_sync_service()

    try:
        result = await sync_service.get_servers(
            search_sn=search_sn,
            search_product_models=search_product_models,
            page=page,
            limit=limit
        )
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.get("/servers/{server_sn}/test-details")
async def get_test_details(
    server_sn: str,
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """查询某服务器的测试详情"""
    sync_service = get_sync_service()

    try:
        result = await sync_service.get_test_details(
            server_sn=server_sn,
            page=page,
            limit=limit
        )
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.get("/jobs")
async def get_jobs(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """查询同步历史记录"""
    sync_service = get_sync_service()

    try:
        result = await sync_service.get_jobs(page=page, limit=limit)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.get("/status")
async def get_status(current_user: dict = Depends(get_current_user)):
    """获取最新同步状态（供前端轮询）"""
    sync_service = get_sync_service()

    try:
        result = await sync_service.get_latest_job_status()
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, error=str(e))

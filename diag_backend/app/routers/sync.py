"""
数据同步路由
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, BackgroundTasks

from ..core.auth import get_current_user
from ..models.response import ApiResponse
from ..services.sync_service import get_sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["数据同步"])


async def _run_sync_background(full: bool = False):
    try:
        svc = get_sync_service()
        await svc.sync_all(full=full)
        logger.info("后台同步完成")
    except Exception as e:
        logger.error(f"后台同步失败: {e}")


@router.post("/trigger")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    full: bool = Query(False, description="True=全量同步, False=增量同步"),
    current_user: dict = Depends(get_current_user)
):
    """手动触发同步，后台执行。默认增量，传 full=true 全量。"""
    svc = get_sync_service()
    if svc.is_running:
        return ApiResponse(success=True, message="同步任务已在运行中")

    background_tasks.add_task(_run_sync_background, full)
    mode = "全量" if full else "增量"
    return ApiResponse(success=True, message=f"{mode}同步任务已启动")


@router.get("/status")
async def get_status(current_user: dict = Depends(get_current_user)):
    """获取同步状态"""
    svc = get_sync_service()
    return ApiResponse(success=True, data={
        "is_running": svc.is_running,
        "servers_count": svc.servers_count,
        "details_count": svc.details_count,
    })


@router.get("/servers")
async def get_servers(
    search_sn: Optional[str] = Query(None, description="服务器 SN 模糊搜索"),
    search_product_models: Optional[str] = Query(None, description="产品型号模糊搜索"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """查询服务器列表"""
    svc = get_sync_service()
    result = await svc.get_servers(
        search_sn=search_sn,
        search_product_models=search_product_models,
        page=page,
        limit=limit
    )
    return ApiResponse(success=True, data=result)


@router.get("/servers/{server_sn}/test-details")
async def get_test_details(
    server_sn: str,
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=500, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """查询某服务器的测试详情"""
    svc = get_sync_service()
    result = await svc.get_test_details(server_sn=server_sn, page=page, limit=limit)
    return ApiResponse(success=True, data=result)


@router.get("/jobs")
async def get_jobs(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(5, ge=1, le=20, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """查询同步历史记录"""
    svc = get_sync_service()
    result = await svc.get_jobs(page=page, limit=limit)
    return ApiResponse(success=True, data=result)

"""
数据同步路由 - 查询已同步数据（只读）
数据写入由独立脚本 (scripts/sync_data.py) 完成
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..core.auth import get_current_user
from ..models.response import ApiResponse
from ..services.sync_service import get_sync_service

router = APIRouter(prefix="/sync", tags=["数据同步"])


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

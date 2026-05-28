from fastapi import APIRouter, Depends, Query
from typing import Optional
from ..models.response import ApiResponse
from ..core.auth import get_current_user
from ..services.error_logs_service import get_error_logs_service

router = APIRouter(prefix="/error-logs", tags=["异常日志"])


@router.get("/stats", response_model=ApiResponse)
async def get_error_stats(
    factory: str = Query(..., description="厂区"),
    time_range: str = Query("day", description="时间范围: day, week, month"),
    current_user: dict = Depends(get_current_user),
):
    """获取异常统计数据（趋势、直通率、问题类型分布、线体拦截数）"""
    service = get_error_logs_service()
    data = await service.get_stats(factory, time_range)
    return ApiResponse(success=True, data=data)


@router.get("/trend", response_model=ApiResponse)
async def get_error_trend(
    factory: str = Query(...),
    time_range: str = Query("day"),
    current_user: dict = Depends(get_current_user),
):
    """获取阻断历史趋势"""
    service = get_error_logs_service()
    data = await service.get_trend(factory, time_range)
    return ApiResponse(success=True, data=data)


@router.get("/stats/yield", response_model=ApiResponse)
async def get_yield_trend(
    factory: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """获取直通率趋势"""
    service = get_error_logs_service()
    data = await service.get_yield_trend(factory)
    return ApiResponse(success=True, data=data)

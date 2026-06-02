"""
数据分析路由 - 异常看板图表数据聚合接口
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.auth import get_current_user
from ..models.api import ApiResponse
from ..services.analytics_service import get_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["数据分析"])


@router.get("/insights")
async def get_dashboard_insights(
    factory_id: Optional[str] = Query(None, description="厂区标识，不传则查全部"),
    search_sn: Optional[str] = Query(None, description="服务器 SN 模糊过滤"),
    search_product_models: Optional[str] = Query(None, description="产品型号过滤"),
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
    trend: str = Query("day", pattern="^(day|week|month)$", description="良率趋势粒度: day/week/month"),
    current_user: dict = Depends(get_current_user),
):
    """获取看板聚合数据（6 组聚合结果）"""
    svc = get_analytics_service()
    data = await svc.get_insights(
        factory_id=factory_id,
        search_sn=search_sn,
        search_product_models=search_product_models,
        days=days,
        trend=trend,
    )
    return ApiResponse(success=True, data=data)

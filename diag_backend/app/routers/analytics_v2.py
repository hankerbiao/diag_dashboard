"""
统计分析 v2 API — 从预计算统计摘要 (test_stats_daily) 读取看板数据

相比 v1 (/api/analytics/insights)，不再对 sync_remote_test_details 做实时聚合，
而是读取 compute_test_stats.py 预先计算好的每日统计摘要，响应更快、数据库负载更低。

保留 v1 接口不变，新旧可同时使用。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.auth import get_current_user
from ..models.api import ApiResponse
from ..services.stats_service import get_stats_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics/v2", tags=["数据分析 v2"])


@router.get("/daily")
async def get_daily_stats(
    factory_id: Optional[str] = Query(None, description="厂区标识"),
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
    current_user: dict = Depends(get_current_user),
):
    """获取每日统计列表"""
    svc = get_stats_service()
    items = await svc.get_daily_stats(factory_id=factory_id, days=days)
    return ApiResponse(success=True, data={"items": items, "total_days": len(items)})


@router.get("/summary")
async def get_summary(
    factory_id: Optional[str] = Query(None, description="厂区标识，不传则查全部"),
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
    current_user: dict = Depends(get_current_user),
):
    """获取汇总统计（跨日聚合，与 v1 insights 格式兼容）"""
    svc = get_stats_service()
    data = await svc.get_summary(factory_id=factory_id, days=days)
    if not data:
        return ApiResponse(success=True, data={})
    return ApiResponse(success=True, data=data)

from fastapi import APIRouter, Depends, Query
from typing import Optional
from ..models.response import ErrorLogsStatsResponse, ApiResponse, TrendDataPoint, YieldDataPoint, StatsByType, LineIssuesData
from ..core.auth import get_current_user

router = APIRouter(prefix="/error-logs", tags=["异常日志"])


@router.get("/stats", response_model=ApiResponse)
async def get_error_stats(
    factory: str = Query(..., description="厂区"),
    time_range: str = Query("day", description="时间范围: day, week, month"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取异常统计数据

    返回趋势图、直通率、问题类型分布、线体拦截数等
    """
    # TODO: 接入 Supabase 真实数据
    # 目前返回模拟数据

    trend_data = {
        "day": [
            {"time": "05-16", "issues": 12},
            {"time": "05-17", "issues": 19},
            {"time": "05-18", "issues": 15},
            {"time": "05-19", "issues": 22},
            {"time": "05-20", "issues": 8},
            {"time": "05-21", "issues": 14},
            {"time": "05-22", "issues": 28},
        ],
        "week": [
            {"time": "W1", "issues": 120},
            {"time": "W2", "issues": 95},
            {"time": "W3", "issues": 140},
            {"time": "W4", "issues": 110},
        ],
        "month": [
            {"time": "Feb", "issues": 450},
            {"time": "Mar", "issues": 400},
            {"time": "Apr", "issues": 520},
            {"time": "May", "issues": 380},
        ]
    }

    yield_data = [
        {"date": "05-16", "yield": 92.5},
        {"date": "05-17", "yield": 93.1},
        {"date": "05-18", "yield": 91.8},
        {"date": "05-19", "yield": 95.4},
        {"date": "05-20", "yield": 96.2},
        {"date": "05-21", "yield": 94.8},
        {"date": "05-22", "yield": 96.5},
    ]

    by_type = [
        {"name": "阻抗异常", "count": 45},
        {"name": "内存自检", "count": 32},
        {"name": "固件缺失", "count": 28},
        {"name": "通讯超时", "count": 18},
        {"name": "总线电压", "count": 12},
    ]

    by_line = [
        {"line": "L1线体", "issues": 12},
        {"line": "L2线体", "issues": 19},
        {"line": "L3线体", "issues": 8},
        {"line": "L4线体", "issues": 24},
        {"line": "L5线体", "issues": 15},
    ]

    return ApiResponse(
        success=True,
        data=ErrorLogsStatsResponse(
            trend=[TrendDataPoint(**d) for d in trend_data.get(time_range, trend_data["day"])],
            yield_trend=[YieldDataPoint(**d) for d in yield_data],
            by_type=[StatsByType(**d) for d in by_type],
            by_line=[LineIssuesData(**d) for d in by_line]
        )
    )


@router.get("/trend", response_model=ApiResponse)
async def get_error_trend(
    factory: str = Query(...),
    time_range: str = Query("day"),
    current_user: dict = Depends(get_current_user)
):
    """获取阻断历史趋势"""
    data = {
        "day": [
            {"time": "05-16", "issues": 12},
            {"time": "05-17", "issues": 19},
            {"time": "05-18", "issues": 15},
            {"time": "05-19", "issues": 22},
            {"time": "05-20", "issues": 8},
            {"time": "05-21", "issues": 14},
            {"time": "05-22", "issues": 28},
        ]
    }

    return ApiResponse(
        success=True,
        data=[TrendDataPoint(**d) for d in data.get(time_range, data["day"])]
    )


@router.get("/stats/yield", response_model=ApiResponse)
async def get_yield_trend(
    factory: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """获取直通率趋势"""
    data = [
        {"date": "05-16", "yield": 92.5},
        {"date": "05-17", "yield": 93.1},
        {"date": "05-18", "yield": 91.8},
        {"date": "05-19", "yield": 95.4},
        {"date": "05-20", "yield": 96.2},
        {"date": "05-21", "yield": 94.8},
        {"date": "05-22", "yield": 96.5},
    ]

    return ApiResponse(
        success=True,
        data=[YieldDataPoint(**d) for d in data]
    )
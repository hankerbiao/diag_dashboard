"""Authenticated user analytics endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..core.auth import get_current_user
from ..models.api import ApiResponse
from ..services.user_analytics_service import get_user_analytics_service

router = APIRouter(prefix="/user-analytics", tags=["用户分析"])


class UsageEventRequest(BaseModel):
    feature: Literal[
        "diagnosis",
        "error_logs",
        "knowledge_base",
        "feedback",
        "user_analytics",
        "settings",
    ]


@router.get("/overview", response_model=ApiResponse)
async def get_user_analytics_overview(
    days: int = Query(30, ge=7, le=90),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=5, le=50),
    search: str | None = Query(None, max_length=100),
    current_user: dict = Depends(get_current_user),
):
    data = await get_user_analytics_service().get_overview(
        days=days,
        page=page,
        limit=limit,
        search=search,
    )
    return ApiResponse(success=True, data=data)


@router.post("/events", response_model=ApiResponse)
async def track_usage_event(
    request: UsageEventRequest,
    current_user: dict = Depends(get_current_user),
):
    await get_user_analytics_service().track_event(current_user, request.feature)
    return ApiResponse(success=True, data={"recorded": True})

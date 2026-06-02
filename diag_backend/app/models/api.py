"""API 通用响应模型"""
from pydantic import BaseModel
from typing import Optional, Any


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    limit: int


class GlobalAiConfigResponse(BaseModel):
    api_key: str
    base_url: str
    model: str
    temperature: float
    provider: str
    updated_at: str
    updated_by: str

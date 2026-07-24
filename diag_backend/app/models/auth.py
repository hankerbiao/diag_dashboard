"""OA 认证请求和响应模型。"""
from typing import Any

from pydantic import BaseModel, Field


class OACallbackRequest(BaseModel):
    status: str
    payload: str
    next: str | None = None


class OAUserResponse(BaseModel):
    id: str
    itcode: str
    name: str
    email: str | None = None
    profile: dict[str, Any] = Field(default_factory=dict)


class OACallbackResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: OAUserResponse


class UserResponse(OAUserResponse):
    """当前登录用户响应。"""

"""应用 Bearer JWT 认证模块。"""
from datetime import timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from .config import get_settings
from .utils import utc_now

settings = get_settings()
security = HTTPBearer()


def create_access_token(
    user_id: str,
    email: str | None = None,
    expires_delta: Optional[timedelta] = None,
    *,
    itcode: str | None = None,
    name: str | None = None,
) -> str:
    """创建应用访问令牌。"""
    expire = utc_now() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode = {
        "sub": user_id,
        "email": email or "",
        "exp": expire
    }
    if itcode:
        to_encode["itcode"] = itcode
    if name:
        to_encode["name"] = name
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """验证 JWT Token，返回用户信息"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        email: str = payload.get("email") or ""
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user id"
            )
        return {
            "id": user_id,
            "email": email,
            "itcode": payload.get("itcode"),
            "name": payload.get("name"),
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )


def get_current_user(user_data: dict = Depends(verify_token)) -> dict:
    """获取当前用户信息"""
    return user_data


def is_admin_user(user_data: dict) -> bool:
    """Return whether the OA ITCode is configured as an administrator."""
    admin_itcodes = {
        value.strip().lower()
        for value in settings.admin_itcodes.split(",")
        if value.strip()
    }
    itcode = str(user_data.get("itcode") or "").strip().lower()
    return bool(itcode and itcode in admin_itcodes)


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Require an administrator ITCode for a protected endpoint."""
    if not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return current_user

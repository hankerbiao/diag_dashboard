"""应用 Bearer JWT 单元测试。"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.core.auth import create_access_token, is_admin_user, require_admin, verify_token
from app.core.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_db_name="test_db",
        jwt_secret_key="test-secret-key-for-testing-only-64-char-string",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
    )


def test_create_access_token_contains_oa_user_data(test_settings: Settings):
    with patch("app.core.auth.settings", test_settings):
        token = create_access_token(
            "user-123",
            "test@example.com",
            itcode="zhangsan",
            name="张三",
        )
        payload = jwt.decode(
            token,
            test_settings.jwt_secret_key,
            algorithms=[test_settings.jwt_algorithm],
        )

    assert payload["sub"] == "user-123"
    assert payload["email"] == "test@example.com"
    assert payload["itcode"] == "zhangsan"
    assert payload["name"] == "张三"
    assert "exp" in payload


def test_create_access_token_allows_missing_email(test_settings: Settings):
    with patch("app.core.auth.settings", test_settings):
        token = create_access_token("user-123", itcode="zhangsan")
        payload = jwt.decode(
            token,
            test_settings.jwt_secret_key,
            algorithms=[test_settings.jwt_algorithm],
        )

    assert payload["email"] == ""


@pytest.mark.asyncio
async def test_verify_token_returns_oa_identity(test_settings: Settings):
    with patch("app.core.auth.settings", test_settings):
        token = create_access_token(
            "user-123",
            "test@example.com",
            itcode="zhangsan",
            name="张三",
        )
        result = await verify_token(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        )

    assert result == {
        "id": "user-123",
        "email": "test@example.com",
        "itcode": "zhangsan",
        "name": "张三",
    }


@pytest.mark.asyncio
async def test_verify_token_rejects_invalid_token(test_settings: Settings):
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")
    with patch("app.core.auth.settings", test_settings):
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(credentials)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_token_rejects_expired_token(test_settings: Settings):
    with patch("app.core.auth.settings", test_settings):
        token = create_access_token(
            "user-123",
            itcode="zhangsan",
            expires_delta=timedelta(seconds=-1),
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(credentials)

    assert exc_info.value.status_code == 401


def test_admin_itcode_matching_is_case_insensitive(test_settings: Settings):
    configured = test_settings.model_copy(update={"admin_itcodes": "libiao1, AdminTwo"})
    with patch("app.core.auth.settings", configured):
        assert is_admin_user({"itcode": "LIBIAO1"}) is True
        assert is_admin_user({"itcode": "admintwo"}) is True
        assert is_admin_user({"itcode": "zhangsan"}) is False


def test_require_admin_rejects_regular_user(test_settings: Settings):
    with patch("app.core.auth.settings", test_settings):
        with pytest.raises(HTTPException) as exc_info:
            require_admin({"itcode": "zhangsan"})
    assert exc_info.value.status_code == 403

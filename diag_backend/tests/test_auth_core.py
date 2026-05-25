"""
核心认证模块单元测试
"""
from datetime import timedelta, datetime
from unittest.mock import patch

import pytest
from jose import jwt

from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
)
from app.core.config import Settings


class TestPasswordHashing:
    """密码哈希测试"""

    def test_hash_password_returns_string(self):
        """哈希密码返回字符串"""
        password = "test_password_123"
        hashed = hash_password(password)

        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password

    def test_hash_password_different_each_time(self):
        """每次哈希结果不同（由于 salt）"""
        password = "test_password_123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2

    def test_verify_password_correct(self):
        """验证正确密码"""
        password = "my_secure_password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """验证错误密码"""
        password = "my_secure_password"
        wrong_password = "wrong_password"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_password(self):
        """验证空密码"""
        password = "my_secure_password"
        hashed = hash_password(password)

        assert verify_password("", hashed) is False


class TestJWTToken:
    """JWT Token 测试"""

    @pytest.fixture
    def test_settings(self) -> Settings:
        """测试配置"""
        return Settings(
            mongodb_uri="mongodb://localhost:27017",
            mongodb_db_name="test_db",
            jwt_secret_key="test-secret-key-for-testing-only-64-char-string",
            jwt_algorithm="HS256",
            access_token_expire_minutes=60,
        )

    def test_create_access_token_returns_string(self, test_settings: Settings):
        """创建 Token 返回字符串"""
        with patch("app.core.auth.settings", test_settings):
            token = create_access_token("user-123", "test@example.com")

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_user_data(self, test_settings: Settings):
        """Token 包含用户数据"""
        user_id = "user-123"
        email = "test@example.com"

        with patch("app.core.auth.settings", test_settings):
            token = create_access_token(user_id, email)
            payload = jwt.decode(
                token,
                test_settings.jwt_secret_key,
                algorithms=[test_settings.jwt_algorithm]
            )

        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert "exp" in payload

    def test_create_access_token_custom_expiry(self, test_settings: Settings):
        """自定义过期时间"""
        user_id = "user-123"
        email = "test@example.com"
        custom_delta = timedelta(minutes=30)

        with patch("app.core.auth.settings", test_settings):
            token = create_access_token(user_id, email, expires_delta=custom_delta)
            payload = jwt.decode(
                token,
                test_settings.jwt_secret_key,
                algorithms=[test_settings.jwt_algorithm]
            )

        # 验证过期时间包含 exp 字段
        assert "exp" in payload

    def test_create_access_token_default_expiry(self, test_settings: Settings):
        """默认过期时间 (60分钟)"""
        user_id = "user-123"
        email = "test@example.com"

        with patch("app.core.auth.settings", test_settings):
            token = create_access_token(user_id, email)
            payload = jwt.decode(
                token,
                test_settings.jwt_secret_key,
                algorithms=[test_settings.jwt_algorithm]
            )

        # 验证过期时间包含 exp 字段
        assert "exp" in payload


class TestVerifyToken:
    """Token 验证测试"""

    @pytest.fixture
    def test_settings(self) -> Settings:
        return Settings(
            mongodb_uri="mongodb://localhost:27017",
            mongodb_db_name="test_db",
            jwt_secret_key="test-secret-key-for-testing-only-64-char-string",
            jwt_algorithm="HS256",
            access_token_expire_minutes=60,
        )

    @pytest.mark.asyncio
    async def test_verify_token_success(self, test_settings: Settings):
        """验证有效 Token"""
        from fastapi.security import HTTPAuthorizationCredentials

        user_id = "user-123"
        email = "test@example.com"

        with patch("app.core.auth.settings", test_settings):
            token = create_access_token(user_id, email)

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.core.auth.settings", test_settings):
            result = await verify_token(credentials)

        assert result["id"] == user_id
        assert result["email"] == email

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, test_settings: Settings):
        """验证无效 Token"""
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")

        with patch("app.core.auth.settings", test_settings):
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_token_expired(self, test_settings: Settings):
        """验证过期 Token"""
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        user_id = "user-123"
        email = "test@example.com"

        # 创建已过期的 Token
        with patch("app.core.auth.settings", test_settings):
            token = create_access_token(
                user_id, email,
                expires_delta=timedelta(seconds=-1)  # 已过期
            )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.core.auth.settings", test_settings):
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(credentials)

        assert exc_info.value.status_code == 401
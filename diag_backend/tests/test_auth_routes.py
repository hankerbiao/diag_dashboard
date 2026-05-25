"""
认证路由 API 测试
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.core.auth import hash_password


class TestAuthRegister:
    """注册接口测试"""

    @pytest.mark.asyncio
    async def test_register_success(self, async_client):
        """注册成功"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_result = MagicMock()
        mock_result.inserted_id = ObjectId()
        mock_collection.insert_one = AsyncMock(return_value=mock_result)

        with patch("app.routers.auth.get_collection", return_value=mock_collection):
            response = await async_client.post(
                "/api/auth/register",
                json={"email": "newuser@example.com", "password": "password123"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["email"] == "newuser@example.com"
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, async_client):
        """重复邮箱注册失败"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value={"email": "existing@example.com"})

        with patch("app.routers.auth.get_collection", return_value=mock_collection):
            response = await async_client.post(
                "/api/auth/register",
                json={"email": "existing@example.com", "password": "password123"}
            )

        assert response.status_code == 400
        data = response.json()
        assert "Email already registered" in data["detail"]

    @pytest.mark.asyncio
    async def test_register_invalid_email_format(self, async_client):
        """无效邮箱格式"""
        response = await async_client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "password123"}
        )

        assert response.status_code == 422  # Validation error


class TestAuthLogin:
    """登录接口测试"""

    @pytest.mark.asyncio
    async def test_login_success(self, async_client, test_user_with_hash: dict):
        """登录成功"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value={
            "_id": ObjectId(),
            "email": test_user_with_hash["email"],
            "password_hash": test_user_with_hash["password_hash"]
        })

        with patch("app.routers.auth.get_collection", return_value=mock_collection):
            response = await async_client.post(
                "/api/auth/login",
                json={
                    "email": test_user_with_hash["email"],
                    "password": test_user_with_hash["password"]
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, async_client):
        """密码错误"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value={
            "_id": ObjectId(),
            "email": "test@example.com",
            "password_hash": hash_password("correct_password")
        })

        with patch("app.routers.auth.get_collection", return_value=mock_collection):
            response = await async_client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "wrong_password"
                }
            )

        assert response.status_code == 401
        data = response.json()
        assert "Invalid email or password" in data["detail"]

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, async_client):
        """用户不存在"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)

        with patch("app.routers.auth.get_collection", return_value=mock_collection):
            response = await async_client.post(
                "/api/auth/login",
                json={
                    "email": "nonexistent@example.com",
                    "password": "password123"
                }
            )

        assert response.status_code == 401


class TestAuthMe:
    """获取当前用户接口测试"""

    @pytest.mark.asyncio
    async def test_get_me_success(self, async_client, auth_headers: dict):
        """获取当前用户成功"""
        response = await async_client.get(
            "/api/auth/me",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-user-id-123"
        assert data["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_me_no_token(self, async_client):
        """无 Token 访问"""
        response = await async_client.get("/api/auth/me")

        assert response.status_code == 401  # No credentials

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, async_client):
        """无效 Token"""
        headers = {"Authorization": "Bearer invalid-token"}

        response = await async_client.get("/api/auth/me", headers=headers)

        assert response.status_code == 401
"""
设置路由 API 测试
"""
from unittest.mock import AsyncMock, patch

import pytest


class TestGetSettings:
    """获取设置接口测试"""

    @pytest.mark.asyncio
    async def test_get_settings_success(self, async_client, auth_headers: dict):
        """获取设置成功"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value={
            "user_id": "test-user-id-123",
            "ai_api_url": "https://api.openai.com",
            "ai_model": "gpt-4",
            "ai_temperature": 0.7,
            "active_kbs": ["kb-1", "kb-2"]
        })

        with patch("app.routers.settings.get_collection", return_value=mock_collection):
            response = await async_client.get(
                "/api/settings",
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["ai_model"] == "gpt-4"
        assert data["data"]["ai_temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_get_settings_default_values(self, async_client, auth_headers: dict):
        """获取默认设置（新用户）"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.insert_one = AsyncMock()

        with patch("app.routers.settings.get_collection", return_value=mock_collection):
            response = await async_client.get(
                "/api/settings",
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 默认值
        assert data["data"]["ai_model"] == "gpt-4-turbo"
        assert data["data"]["ai_temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_get_settings_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.get("/api/settings")
        assert response.status_code == 401


class TestUpdateSettings:
    """更新设置接口测试"""

    @pytest.mark.asyncio
    async def test_update_settings_success(self, async_client, auth_headers: dict):
        """更新设置成功"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value={
            "user_id": "test-user-id-123",
            "ai_model": "gpt-4"
        })
        mock_collection.update_one = AsyncMock()

        with patch("app.routers.settings.get_collection", return_value=mock_collection):
            response = await async_client.put(
                "/api/settings",
                headers=auth_headers,
                json={
                    "ai_model": "gpt-4",
                    "ai_temperature": 0.9
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_update_settings_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.put(
            "/api/settings",
            json={"ai_temperature": 0.9}
        )
        assert response.status_code == 401
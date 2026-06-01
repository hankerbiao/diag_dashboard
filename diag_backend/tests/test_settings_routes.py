"""
设置路由 API 测试
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.services.llm_service import llm_service
from app.core.auth import create_access_token


@pytest.fixture
def admin_headers() -> dict:
    """管理员认证请求头"""
    token = create_access_token(
        user_id="admin-user-id",
        email="admin@example.com",
    )
    return {"Authorization": f"Bearer {token}"}


class TestGetAiConfig:
    """全局 AI 配置查询接口测试"""

    @pytest.mark.asyncio
    async def test_get_ai_config_success(self, async_client, auth_headers: dict):
        """获取全局 AI 配置成功"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value={
            "_id": "ai_config",
            "api_key": "sk-test-key-12345",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4-turbo",
            "temperature": 0.7,
            "provider": "openai",
            "updated_by": "system",
            "updated_at": "2026-05-27T00:00:00Z",
        })

        with patch("app.routers.settings.get_collection", return_value=mock_collection):
            response = await async_client.get(
                "/api/settings/ai-config",
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # API Key 已脱敏: "sk-test-key-12345" → "sk-****345"
        assert data["data"]["api_key"] == "sk-****345"
        assert data["data"]["model"] == "gpt-4-turbo"
        assert data["data"]["temperature"] == 0.7
        assert data["data"]["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_get_ai_config_not_found_fallback_env(self, async_client, auth_headers: dict):
        """数据库无配置时回退到环境变量"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)

        with patch("app.routers.settings.get_collection", return_value=mock_collection):
            response = await async_client.get(
                "/api/settings/ai-config",
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 回退到环境变量默认值
        assert "model" in data["data"]

    @pytest.mark.asyncio
    async def test_get_ai_config_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.get("/api/settings/ai-config")
        assert response.status_code == 401


class TestUpdateAiConfig:
    """全局 AI 配置更新接口测试"""

    @pytest.mark.asyncio
    async def test_update_ai_config_success(self, async_client, admin_headers: dict):
        """更新全局 AI 配置成功"""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock()
        mock_collection.update_one = AsyncMock()

        with (
            patch("app.routers.settings.get_collection", return_value=mock_collection),
            patch.object(llm_service, "reload_config", AsyncMock()),
        ):
            response = await async_client.put(
                "/api/settings/ai-config",
                headers=admin_headers,
                json={
                    "api_key": "sk-new-key",
                    "base_url": "https://new.api.com/v1",
                    "model": "gpt-4o",
                    "temperature": 0.5,
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # 验证 update_one 被正确调用
        call_args = mock_collection.update_one.call_args
        assert call_args is not None
        assert call_args[0][0] == {"_id": "ai_config"}
        set_data = call_args[0][1]["$set"]
        assert set_data["model"] == "gpt-4o"
        assert set_data["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_update_ai_config_partial(self, async_client, admin_headers: dict):
        """部分更新 AI 配置"""
        mock_collection = AsyncMock()
        mock_collection.update_one = AsyncMock()

        with (
            patch("app.routers.settings.get_collection", return_value=mock_collection),
            patch.object(llm_service, "reload_config", AsyncMock()),
        ):
            response = await async_client.put(
                "/api/settings/ai-config",
                headers=admin_headers,
                json={"model": "gpt-4o"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        set_data = mock_collection.update_one.call_args[0][1]["$set"]
        assert set_data["model"] == "gpt-4o"
        # 未提供的字段不应出现在 set 中
        assert "api_key" not in set_data
        assert "temperature" not in set_data

    @pytest.mark.asyncio
    async def test_update_ai_config_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.put(
            "/api/settings/ai-config",
            json={"model": "gpt-4o"}
        )
        assert response.status_code == 401

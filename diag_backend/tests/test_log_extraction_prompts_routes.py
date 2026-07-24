"""
提取 prompt / 机型 配置接口测试（新增端点）。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fake_registry():
    reg = MagicMock()
    reg.list_prompts = AsyncMock(
        return_value=[
            {
                "model": "default",
                "is_default": True,
                "system_prompt": "s",
                "user_template": "t",
                "updated_at": "",
                "updated_by": "",
            },
        ]
    )
    reg.upsert = AsyncMock()
    reg.delete = AsyncMock()
    return reg


class TestMachineModels:
    @pytest.mark.asyncio
    async def test_get_machine_models_from_devices(
        self, async_client, auth_headers: dict
    ):
        def fake_get_collection(name: str):
            c = AsyncMock()
            if name == "devices":
                c.distinct = AsyncMock(return_value=["X1", "X2", "", None])
            else:
                c.distinct = AsyncMock(return_value=[])
            return c

        with patch(
            "app.routers.settings.get_collection", side_effect=fake_get_collection
        ):
            response = await async_client.get(
                "/api/settings/machine-models", headers=auth_headers
            )

        assert response.status_code == 200
        # 设备机型聚合去重并过滤空值；非空时不回退 product_models
        assert response.json()["data"]["models"] == ["X1", "X2"]

    @pytest.mark.asyncio
    async def test_get_machine_models_fallback_to_product_models(
        self, async_client, auth_headers: dict
    ):
        def fake_get_collection(name: str):
            c = AsyncMock()
            if name == "devices":
                c.distinct = AsyncMock(return_value=[])
            elif name == "sync_remote_servers":
                c.distinct = AsyncMock(return_value=["A,B", "C"])
            else:
                c.distinct = AsyncMock(return_value=[])
            return c

        with patch(
            "app.routers.settings.get_collection", side_effect=fake_get_collection
        ):
            response = await async_client.get(
                "/api/settings/machine-models", headers=auth_headers
            )

        assert response.status_code == 200
        # devices 为空时回退到 product_models，按逗号拆分并去重
        assert response.json()["data"]["models"] == ["A", "B", "C"]

    @pytest.mark.asyncio
    async def test_get_machine_models_includes_manually_configured_prompts(
        self, async_client, auth_headers: dict
    ):
        def fake_get_collection(name: str):
            c = AsyncMock()
            if name == "devices":
                c.distinct = AsyncMock(return_value=["X1"])
            elif name == "log_extraction_prompts":
                c.distinct = AsyncMock(return_value=["default", "Manual-X2", "X1"])
            else:
                c.distinct = AsyncMock(return_value=[])
            return c

        with patch(
            "app.routers.settings.get_collection", side_effect=fake_get_collection
        ):
            response = await async_client.get(
                "/api/settings/machine-models", headers=auth_headers
            )

        assert response.status_code == 200
        assert response.json()["data"]["models"] == ["X1", "Manual-X2"]

    @pytest.mark.asyncio
    async def test_get_machine_models_unauthorized(self, async_client):
        response = await async_client.get("/api/settings/machine-models")
        assert response.status_code == 401


class TestLogExtractionPrompts:
    @pytest.mark.asyncio
    async def test_list_prompts_success(self, async_client, auth_headers: dict):
        with patch(
            "app.routers.settings.PromptRegistry", return_value=_fake_registry()
        ):
            response = await async_client.get(
                "/api/settings/log-extraction/prompts", headers=auth_headers
            )
        assert response.status_code == 200
        assert response.json()["data"]["prompts"][0]["model"] == "default"

    @pytest.mark.asyncio
    async def test_upsert_prompt_success(self, async_client, auth_headers: dict):
        reg = _fake_registry()
        with patch("app.routers.settings.PromptRegistry", return_value=reg):
            response = await async_client.put(
                "/api/settings/log-extraction/prompts",
                headers=auth_headers,
                json={
                    "model": "X1",
                    "system_prompt": "sys",
                    "user_template": "log={log_text}",
                },
            )
        assert response.status_code == 200
        reg.upsert.assert_awaited_once()
        assert reg.upsert.call_args[0][0] == "X1"

    @pytest.mark.asyncio
    async def test_delete_prompt_success(self, async_client, auth_headers: dict):
        reg = _fake_registry()
        with patch("app.routers.settings.PromptRegistry", return_value=reg):
            response = await async_client.delete(
                "/api/settings/log-extraction/prompts/X1", headers=auth_headers
            )
        assert response.status_code == 200
        reg.delete.assert_awaited_once_with("X1")

    @pytest.mark.asyncio
    async def test_delete_default_rejected(self, async_client, auth_headers: dict):
        reg = _fake_registry()
        reg.delete = AsyncMock(side_effect=ValueError("默认 prompt 不可删除"))
        with patch("app.routers.settings.PromptRegistry", return_value=reg):
            response = await async_client.delete(
                "/api/settings/log-extraction/prompts/default", headers=auth_headers
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_endpoints_unauthorized(self, async_client):
        assert (
            await async_client.get("/api/settings/log-extraction/prompts")
        ).status_code == 401
        assert (
            await async_client.put(
                "/api/settings/log-extraction/prompts",
                json={"model": "X1", "system_prompt": "s", "user_template": "t"},
            )
        ).status_code == 401
        assert (
            await async_client.delete("/api/settings/log-extraction/prompts/X1")
        ).status_code == 401

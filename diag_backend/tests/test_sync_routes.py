"""
MES 实时查询路由测试（/api/sync/servers*）
数据写入由 scripts/weaveeye_sync.py 完成
"""
from unittest.mock import AsyncMock, patch


class TestSyncServers:
    """服务器列表（MES 直连）"""

    async def test_get_servers_requires_factory(self, async_client, auth_headers: dict):
        response = await async_client.get("/api/sync/servers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["items"] == []

    async def test_get_servers_mes_success(self, async_client, auth_headers: dict):
        mock_mes = AsyncMock()
        mock_mes.search_servers = AsyncMock(return_value={
            "items": [{"server_sn": "SN001"}],
            "total": 1,
            "page": 1,
            "limit": 20,
        })
        mock_mes.__aenter__ = AsyncMock(return_value=mock_mes)
        mock_mes.__aexit__ = AsyncMock(return_value=None)

        with patch("app.routers.sync.MESDirectService", return_value=mock_mes):
            response = await async_client.get(
                "/api/sync/servers",
                headers=auth_headers,
                params={"factory_id": "kunshan"},
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_get_servers_unauthorized(self, async_client):
        response = await async_client.get("/api/sync/servers")
        assert response.status_code == 401

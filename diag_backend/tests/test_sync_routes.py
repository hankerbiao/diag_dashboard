"""
同步路由 API 测试（只读查询端点）
数据写入由独立脚本 scripts/sync_data.py 完成
"""
from unittest.mock import AsyncMock, MagicMock, patch


class TestSyncJobs:
    """同步任务列表接口测试"""

    async def test_get_jobs_success(self, async_client, auth_headers: dict):
        """获取任务列表成功"""
        mock_service = MagicMock()
        mock_service.get_jobs = AsyncMock(return_value={
            "items": [
                {
                    "id": "job-1",
                    "status": "success",
                    "started_at": "2024-01-15T10:00:00",
                    "finished_at": "2024-01-15T10:30:00",
                    "servers_total": 50,
                    "servers_new": 10
                }
            ],
            "total": 1,
            "page": 1,
            "limit": 20
        })

        with patch("app.routers.sync.get_sync_service", return_value=mock_service):
            response = await async_client.get(
                "/api/sync/jobs",
                headers=auth_headers,
                params={"page": 1, "limit": 20}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["items"]) == 1

    async def test_get_jobs_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.get("/api/sync/jobs")
        assert response.status_code == 401


class TestSyncServers:
    """服务器列表接口测试"""

    async def test_get_servers_success(self, async_client, auth_headers: dict):
        """获取服务器列表成功"""
        mock_service = MagicMock()
        mock_service.get_servers = AsyncMock(return_value={
            "items": [
                {"id": "server-1", "server_sn": "SN001", "model": "GServer"}
            ],
            "total": 1,
            "page": 1,
            "limit": 20
        })

        with patch("app.routers.sync.get_sync_service", return_value=mock_service):
            response = await async_client.get(
                "/api/sync/servers",
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_get_servers_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.get("/api/sync/servers")
        assert response.status_code == 401

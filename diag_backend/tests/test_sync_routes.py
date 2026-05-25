"""
同步路由 API 测试
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSyncTrigger:
    """触发同步接口测试"""

    @pytest.mark.asyncio
    async def test_trigger_sync_success(self, async_client, auth_headers: dict):
        """触发同步成功"""
        mock_service = MagicMock()
        mock_service.get_latest_job_status = AsyncMock(return_value=None)

        with patch("app.routers.sync.get_sync_service", return_value=mock_service):
            response = await async_client.post(
                "/api/sync/trigger",
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_trigger_sync_already_running(self, async_client, auth_headers: dict):
        """同步任务已在运行"""
        mock_service = MagicMock()
        mock_service.get_latest_job_status = AsyncMock(return_value={
            "id": "job-running-123",
            "status": "running"
        })

        with patch("app.routers.sync.get_sync_service", return_value=mock_service):
            response = await async_client.post(
                "/api/sync/trigger",
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "已在运行" in data["message"]

    @pytest.mark.asyncio
    async def test_trigger_sync_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.post("/api/sync/trigger")
        assert response.status_code == 401


class TestSyncStatus:
    """同步状态接口测试"""

    @pytest.mark.asyncio
    async def test_get_status_success(self, async_client, auth_headers: dict):
        """获取同步状态成功"""
        mock_service = MagicMock()
        mock_service.get_latest_job_status = AsyncMock(return_value={
            "id": "job-123",
            "status": "success",
            "started_at": "2024-01-15T10:00:00"
        })

        with patch("app.routers.sync.get_sync_service", return_value=mock_service):
            response = await async_client.get(
                "/api/sync/status",
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_get_status_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.get("/api/sync/status")
        assert response.status_code == 401


class TestSyncJobs:
    """同步任务列表接口测试"""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_get_jobs_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.get("/api/sync/jobs")
        assert response.status_code == 401


class TestSyncServers:
    """服务器列表接口测试"""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_get_servers_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.get("/api/sync/servers")
        assert response.status_code == 401
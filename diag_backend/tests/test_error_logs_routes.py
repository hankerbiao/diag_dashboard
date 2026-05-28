"""
错误日志路由 API 测试
"""
from unittest.mock import AsyncMock, patch

import pytest


class TestErrorLogsStats:
    """错误日志统计接口测试"""

    @pytest.mark.asyncio
    async def test_get_stats_missing_factory(self, async_client, auth_headers: dict):
        """缺少工厂参数"""
        response = await async_client.get(
            "/api/error-logs/stats",
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_get_stats_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.get(
            "/api/error-logs/stats",
            params={"factory": "Factory-A"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_stats_success(self, async_client, auth_headers: dict):
        """获取统计成功"""
        mock_data = {
            "trend": [{"time": "2026-05-20", "issues": 12}],
            "yield_trend": [{"date": "2026-05-20", "total": 100, "passed": 95, "failed": 5, "yield": 95.0}],
            "by_type": [{"name": "硬件故障", "count": 45}],
            "by_line": [{"line": "CPU测试", "issues": 12}],
        }
        mock_service = AsyncMock()
        mock_service.get_stats = AsyncMock(return_value=mock_data)

        with patch("app.routers.error_logs.get_error_logs_service", return_value=mock_service):
            response = await async_client.get(
                "/api/error-logs/stats",
                params={"factory": "kunshan", "time_range": "day"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["trend"] == mock_data["trend"]
        assert data["data"]["yield_trend"] == mock_data["yield_trend"]
        assert data["data"]["by_type"] == mock_data["by_type"]
        assert data["data"]["by_line"] == mock_data["by_line"]


class TestErrorLogsTrend:
    """错误日志趋势接口测试"""

    @pytest.mark.asyncio
    async def test_get_trend_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.get(
            "/api/error-logs/trend",
            params={"factory": "Factory-A", "time_range": "week"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_trend_success(self, async_client, auth_headers: dict):
        """获取趋势成功"""
        mock_data = [{"time": "2026-05-20", "issues": 12}]
        mock_service = AsyncMock()
        mock_service.get_trend = AsyncMock(return_value=mock_data)

        with patch("app.routers.error_logs.get_error_logs_service", return_value=mock_service):
            response = await async_client.get(
                "/api/error-logs/trend",
                params={"factory": "kunshan", "time_range": "day"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == mock_data


class TestErrorLogsYield:
    """直通率趋势接口测试"""

    @pytest.mark.asyncio
    async def test_get_yield_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.get(
            "/api/error-logs/stats/yield",
            params={"factory": "Factory-A", "time_range": "month"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_yield_success(self, async_client, auth_headers: dict):
        """获取直通率成功"""
        mock_data = [{"date": "2026-05-20", "total": 100, "passed": 95, "failed": 5, "yield": 95.0}]
        mock_service = AsyncMock()
        mock_service.get_yield_trend = AsyncMock(return_value=mock_data)

        with patch("app.routers.error_logs.get_error_logs_service", return_value=mock_service):
            response = await async_client.get(
                "/api/error-logs/stats/yield",
                params={"factory": "kunshan"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == mock_data

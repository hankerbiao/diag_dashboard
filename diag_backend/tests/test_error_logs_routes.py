"""
错误日志路由 API 测试
"""
from unittest.mock import AsyncMock, MagicMock, patch

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
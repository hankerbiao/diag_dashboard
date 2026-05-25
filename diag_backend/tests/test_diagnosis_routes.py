"""
诊断路由 API 测试
"""
from unittest.mock import AsyncMock, patch

import pytest


class TestDiagnosisSN:
    """SN 诊断接口测试"""

    @pytest.mark.asyncio
    async def test_diagnose_sn_success(
        self,
        async_client,
        auth_headers: dict,
        sample_device_info: dict,
        sample_diagnosis_result: dict
    ):
        """SN 诊断成功"""
        with patch("app.routers.diagnosis.knowledge_graph") as mock_kg:
            # Mock 知识图谱返回
            mock_kg.get_device_by_sn = AsyncMock(return_value=sample_device_info)
            mock_kg.get_device_test_logs = AsyncMock(return_value=[])
            mock_kg.get_device_maintenance_history = AsyncMock(return_value=[])
            mock_kg.find_similar_cases = AsyncMock(return_value=[])

            with patch("app.routers.diagnosis.llm_service") as mock_llm:
                mock_llm.diagnose_sn = AsyncMock(return_value=sample_diagnosis_result)

                response = await async_client.post(
                    "/api/diagnosis/sn",
                    headers=auth_headers,
                    json={"sn": "SN12345678", "factory": "Factory-A"}
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    @pytest.mark.asyncio
    async def test_diagnose_sn_device_not_found(self, async_client, auth_headers: dict):
        """设备未找到"""
        with patch("app.routers.diagnosis.knowledge_graph") as mock_kg:
            mock_kg.get_device_by_sn = AsyncMock(return_value=None)

            response = await async_client.post(
                "/api/diagnosis/sn",
                headers=auth_headers,
                json={"sn": "NONEXISTENT", "factory": "Factory-A"}
            )

        assert response.status_code == 200  # 返回 200 但 success=False
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_diagnose_sn_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.post(
            "/api/diagnosis/sn",
            json={"sn": "SN12345678", "factory": "Factory-A"}
        )

        assert response.status_code == 401


class TestDiagnosisErrorLog:
    """错误日志分析接口测试"""

    @pytest.mark.asyncio
    async def test_analyze_error_log_unauthorized(self, async_client):
        """未授权访问"""
        response = await async_client.post("/api/diagnosis/error-log/error-001")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_analyze_error_log_returns_response(self, async_client, auth_headers: dict):
        """错误日志分析返回响应"""
        response = await async_client.post(
            "/api/diagnosis/error-log/error-001",
            headers=auth_headers
        )

        # 应该返回 200（无论成功或失败）
        assert response.status_code == 200
        data = response.json()
        # 检查响应结构
        assert "success" in data
        assert "data" in data
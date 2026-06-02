"""
诊断路由 API 测试
"""
from typing import List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _mes_mock(items: Optional[List] = None):
    """Mock MESDirectService 上下文，返回指定测试明细列表。"""
    if items is None:
        items = [
            {
                "server_test_result": "失败",
                "detailed_flow": "Stress Check",
                "test_time": "2026-05-14 21:27:48",
                "fault_type1": "阻抗异常",
            }
        ]

    mock_mes = AsyncMock()
    mock_mes.get_test_details = AsyncMock(
        return_value={"items": items, "total": len(items)}
    )
    mock_mes.get_server = AsyncMock(return_value=None)
    mock_mes.__aenter__ = AsyncMock(return_value=mock_mes)
    mock_mes.__aexit__ = AsyncMock(return_value=None)
    return patch("app.routers.diagnosis.MESDirectService", return_value=mock_mes)


def _factory_mock(factory_id: str = "Factory-A"):
    return patch(
        "app.routers.diagnosis.get_factory_by_id",
        return_value={
            "factory_id": factory_id,
            "name": "测试厂区",
            "base_url": "http://10.0.0.1",
            "log_base_url": "http://10.0.0.2/log",
        },
    )


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
        mock_collection = Mock()
        mock_collection.find = Mock(return_value=mock_collection)
        mock_collection.sort = Mock(return_value=mock_collection)
        mock_collection.limit = Mock(return_value=mock_collection)
        mock_collection.to_list = AsyncMock(return_value=[])
        mock_collection.find_one = AsyncMock(return_value=None)

        with _factory_mock(), _mes_mock():
            with patch("app.routers.diagnosis.knowledge_graph") as mock_kg:
                mock_kg.get_device_by_sn = AsyncMock(return_value=sample_device_info)
                mock_kg.get_device_test_logs = AsyncMock(return_value=[])
                mock_kg.get_device_maintenance_history = AsyncMock(return_value=[])
                mock_kg.find_similar_cases = AsyncMock(return_value=[])

                with patch("app.routers.diagnosis.llm_service") as mock_llm:
                    mock_llm.diagnose_sn = AsyncMock(return_value=sample_diagnosis_result)

                    with patch("app.routers.diagnosis.get_collection", return_value=mock_collection):
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
    async def test_diagnose_sn_invalid_factory(self, async_client, auth_headers: dict):
        """厂区不存在时应返回明确错误"""
        with patch("app.routers.diagnosis.get_factory_by_id", return_value=None):
            response = await async_client.post(
                "/api/diagnosis/sn",
                headers=auth_headers,
                json={"sn": "NONEXISTENT", "factory": "invalid-factory"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "厂区不存在" in data["error"]

    @pytest.mark.asyncio
    async def test_diagnose_sn_sims_only_device(
        self, async_client, auth_headers: dict, sample_diagnosis_result: dict
    ):
        """MongoDB 无设备记录，但 SIMS 有数据时仍可诊断"""
        mock_collection = Mock()
        mock_collection.find = Mock(return_value=mock_collection)
        mock_collection.sort = Mock(return_value=mock_collection)
        mock_collection.limit = Mock(return_value=mock_collection)
        mock_collection.to_list = AsyncMock(return_value=[])
        mock_collection.find_one = AsyncMock(return_value={"_id": "test1", "server_sn": "SN-REALDATA"})

        with _factory_mock(), _mes_mock():
            with patch("app.routers.diagnosis.knowledge_graph") as mock_kg:
                mock_kg.get_device_by_sn = AsyncMock(return_value=None)
                mock_kg.get_device_test_logs = AsyncMock(return_value=[])
                mock_kg.get_device_maintenance_history = AsyncMock(return_value=[])
                mock_kg.find_similar_cases = AsyncMock(return_value=[])

                with patch("app.routers.diagnosis.llm_service") as mock_llm:
                    mock_llm.diagnose_sn = AsyncMock(return_value=sample_diagnosis_result)

                    with patch("app.routers.diagnosis.get_collection", return_value=mock_collection):
                        response = await async_client.post(
                            "/api/diagnosis/sn",
                            headers=auth_headers,
                            json={"sn": "SN-REALDATA", "factory": "Factory-A"}
                        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    @pytest.mark.asyncio
    async def test_diagnose_sn_sims_empty(
        self, async_client, auth_headers: dict, sample_device_info: dict
    ):
        """SIMS 返回空测试记录时应提前终止，不调用大模型"""
        mock_collection = Mock()
        mock_collection.find_one = AsyncMock(return_value=None)

        with _factory_mock(), _mes_mock(items=[]):
            with patch("app.routers.diagnosis.knowledge_graph") as mock_kg:
                mock_kg.get_device_by_sn = AsyncMock(return_value=sample_device_info)

                with patch("app.routers.diagnosis.llm_service") as mock_llm:
                    mock_llm.diagnose_sn = AsyncMock()

                    with patch("app.routers.diagnosis.get_collection", return_value=mock_collection):
                        response = await async_client.post(
                            "/api/diagnosis/sn",
                            headers=auth_headers,
                            json={"sn": "SN-EMPTY", "factory": "Factory-A"},
                        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "SIMS 未查询到" in data["error"]
        mock_llm.diagnose_sn.assert_not_called()

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
"""测试详情合成 ID 与异常日志解析"""
from unittest.mock import AsyncMock, patch

import pytest

from app.models.request import ErrorLogAnalyzeContext
from app.routers.diagnosis import (
    _parse_mes_client_detail_id,
    _get_error_log_detail,
)


class TestParseMesClientDetailId:
    def test_tongxiang_with_datetime_spaces(self):
        raw_id = "tongxiang_6102202904362178_2026-06-02 10:39:45_0"
        parsed = _parse_mes_client_detail_id(raw_id)
        assert parsed is not None
        assert parsed["factory_id"] == "tongxiang"
        assert parsed["server_sn"] == "6102202904362178"
        assert parsed["test_time"] == "2026-06-02 10:39:45"
        assert parsed["idx"] == 0

    def test_invalid_id(self):
        assert _parse_mes_client_detail_id("not-a-valid-id") is None


class TestGetErrorLogDetailMesFallback:
    @pytest.mark.asyncio
    async def test_resolves_mes_synthetic_id(self):
        error_log_id = "tongxiang_SN001_2026-06-02 10:39:45_0"
        mes_items = [
            {
                "factory_id": "tongxiang",
                "server_sn": "SN001",
                "test_time": "2026-06-02 10:39:45",
                "detailed_flow": "Stress",
                "server_test_result": "不通过",
                "log_path": "/log//SN001/test.log",
                "fault_type1": "x",
                "fault_type2": "",
                "fault_type3": "",
            }
        ]
        mock_mes = AsyncMock()
        mock_mes.get_test_details = AsyncMock(
            return_value={"items": mes_items, "total": 1}
        )
        mock_mes.__aenter__ = AsyncMock(return_value=mock_mes)
        mock_mes.__aexit__ = AsyncMock(return_value=None)

        mock_col = AsyncMock()
        mock_col.find_one = AsyncMock(return_value=None)

        with patch("app.routers.diagnosis.get_collection", return_value=mock_col):
            with patch("app.routers.diagnosis.MESDirectService", return_value=mock_mes):
                with patch(
                    "app.routers.diagnosis.knowledge_graph.get_error_log_by_id",
                    AsyncMock(return_value=None),
                ):
                    detail = await _get_error_log_detail(error_log_id)

        assert detail is not None
        assert detail["sn"] == "SN001"
        assert detail["log_path"] == "/log//SN001/test.log"


class TestGetErrorLogDetailFromContext:
    @pytest.mark.asyncio
    async def test_uses_posted_context_without_mes(self):
        ctx = ErrorLogAnalyzeContext(
            factory_id="datong",
            server_sn="6102261604345142",
            test_time="2026-06-02 15:33:34",
            test_item="Stress",
            fail_details="不通过",
            log_path="/6102261604345142/2078_test.log",
        )
        with patch(
            "app.routers.diagnosis.knowledge_graph.get_error_log_by_id",
            AsyncMock(return_value=None),
        ):
            detail = await _get_error_log_detail("datong_610226_2026-06-02 15:33:34_0", ctx)
        assert detail is not None
        assert detail["sn"] == "6102261604345142"
        assert detail["log_path"] == "/6102261604345142/2078_test.log"

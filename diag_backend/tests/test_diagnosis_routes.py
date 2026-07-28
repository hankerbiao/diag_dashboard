"""
诊断路由 API 测试
"""
import json
from typing import List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.routers import diagnosis as diagnosis_router
from app.services.llm_service import LLMResponseParseError
from app.services.mes_direct_service import ServerInfo


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


def _prompt_mock(model: str = "default"):
    return patch(
        "app.routers.diagnosis.PromptRegistry.get_prompt",
        new=AsyncMock(
            return_value={
                "model": model,
                "system_prompt": "system",
                "user_template": "log={log_text}",
            }
        ),
    )


class TestDiagnosisLogContent:
    """SN 原始日志下载接口测试。"""

    def test_bounded_download_collector_preserves_head_tail_and_metadata(self):
        collector = diagnosis_router._BoundedByteCollector(limit=10)
        collector.feed(b"first\n")
        collector.feed(b"middle\nlast")

        raw, metadata = collector.result()

        assert raw.startswith(b"first")
        assert raw.endswith(b"\nlast")
        assert b"middle omitted" in raw
        assert metadata == {
            "source_size": 17,
            "downloaded_size": 10,
            "source_line_count": 3,
            "source_truncated": True,
            "truncation_strategy": "head_tail",
        }

    @pytest.mark.asyncio
    async def test_download_uses_full_log_fetcher(self, async_client, auth_headers: dict):
        full_content = "line 1\nline 2\nline 3"
        with _factory_mock("tongxiang"), patch(
            "app.routers.diagnosis._download_log_tail_fetch_full",
            new=AsyncMock(return_value=(full_content, None)),
        ) as download_full:
            response = await async_client.post(
                "/api/diagnosis/sn/log-content",
                params={"log_path": "SN001/test.log"},
                headers=auth_headers,
                json={"sn": "SN001", "factory": "tongxiang"},
            )

        assert response.status_code == 200
        assert response.json()["data"]["content"] == full_content
        download_full.assert_awaited_once_with(
            "http://10.0.0.2/log",
            "SN001/test.log",
            ftp_user=None,
            ftp_password=None,
        )

    @pytest.mark.asyncio
    async def test_failed_logs_take_latest_two_then_deduplicate_by_test_item(self):
        """按时间取最新两条后按测试项目去重，不使用第三条日志补位。"""
        failed_logs = [
            {
                "test_item": "较旧日志",
                "test_time": "2026-07-23 10:00:00",
                "log_path": "logs/older.log",
            },
            {
                "test_item": "Stress Check",
                "test_time": "2026-07-23 13:00:00",
                "log_path": "logs/latest.log",
            },
            {
                "test_item": "Stress Check",
                "test_time": "2026-07-23 12:00:00",
                "log_path": "logs/second-latest.log",
            },
            {
                "test_item": "更旧日志",
                "test_time": "2026-07-23 09:00:00",
                "log_path": "logs/oldest.log",
            },
        ]
        extract_log = AsyncMock(
            return_value=(
                "ERROR",
                {"matched_lines": 1, "total_lines": 10, "ai_extracted": False},
            )
        )
        progress_events: list[tuple[str, dict]] = []

        async def capture_progress(
            stage: str,
            _detail: str,
            _status: str = "running",
            metadata: Optional[dict] = None,
        ) -> None:
            progress_events.append((stage, metadata or {}))

        with patch(
            "app.routers.diagnosis._download_and_extract_log", new=extract_log
        ):
            _, downloaded_files = await diagnosis_router._download_failed_item_logs(
                log_base_url="http://10.0.0.2/log",
                failed_logs=failed_logs,
                factory_label="测试厂区",
                on_progress=capture_progress,
            )

        downloaded_paths = [call.args[1] for call in extract_log.await_args_list]
        assert downloaded_paths == ["logs/latest.log"]
        assert [item["log_path"] for item in downloaded_files] == downloaded_paths
        assert progress_events[0] == ("log_download", {"file_count": 1})

    @pytest.mark.asyncio
    async def test_preprocessing_comparison_summary_is_emitted_to_main_progress(self):
        extract_log = AsyncMock(
            return_value=(
                "ERROR fan failed",
                {
                    "error_count": 1,
                    "total_lines": 1000,
                    "ai_extracted": True,
                    "preprocessing_applied": True,
                    "preprocessing_original_lines": 1000,
                    "preprocessing_kept_lines": 125,
                    "preprocessing_removed_lines": 875,
                    "preprocessing_level_lines": 990,
                    "preprocessing_anomaly_entries": 3,
                },
            )
        )
        progress_events: list[tuple[str, str, dict]] = []

        async def capture_progress(
            stage: str,
            detail: str,
            _status: str = "running",
            metadata: Optional[dict] = None,
        ) -> None:
            progress_events.append((stage, detail, metadata or {}))

        with patch(
            "app.routers.diagnosis._download_and_extract_log", new=extract_log
        ):
            await diagnosis_router._download_failed_item_logs(
                log_base_url="http://10.0.0.2/log",
                failed_logs=[
                    {
                        "test_item": "Stress Check",
                        "test_time": "2026-07-23 13:00:00",
                        "log_path": "logs/latest.log",
                    }
                ],
                factory_label="测试厂区",
                on_progress=capture_progress,
            )

        comparison_events = [
            event for event in progress_events if "log_comparison" in event[2]
        ]
        assert len(comparison_events) == 1
        stage, detail, metadata = comparison_events[0]
        assert stage == "log_merge"
        assert "原文件 1000 行，清洗后 125 行，过滤 875 行（87.5%）" in detail
        assert metadata["log_comparison"] == {
            "test_item": "Stress Check",
            "log_path": "logs/latest.log",
            "original_lines": 1000,
            "kept_lines": 125,
            "removed_lines": 875,
            "removal_rate": 0.875,
            "preprocessing_applied": True,
            "recognized_level_lines": 990,
            "anomaly_entries": 3,
        }

    @pytest.mark.asyncio
    async def test_non_anomalous_log_is_not_added_to_final_analysis(self):
        extract_log = AsyncMock(
            return_value=(
                "[AI 提取 - 共 0 个错误点]",
                {
                    "error_count": 0,
                    "total_lines": 20,
                    "ai_extracted": True,
                },
            )
        )

        with patch(
            "app.routers.diagnosis._download_and_extract_log", new=extract_log
        ):
            markdown, downloaded_files = (
                await diagnosis_router._download_failed_item_logs(
                    log_base_url="http://10.0.0.2/log",
                    failed_logs=[
                        {
                            "test_item": "Stress Check",
                            "test_time": "2026-07-23 13:00:00",
                            "log_path": "logs/normal.log",
                        }
                    ],
                    factory_label="测试厂区",
                )
            )

        assert markdown == ""
        assert downloaded_files == []


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

        with _factory_mock(), _mes_mock(), _prompt_mock("TestModel"):
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
    async def test_gather_resolves_machine_prompt_before_log_extraction(self):
        """Mongo 机型为空时从 MES 回退，并将对应 Prompt 透传给日志提取。"""
        raw_logs = [
            {
                "server_test_result": "失败",
                "detailed_flow": "Stress Check",
                "test_time": "2026-05-14 21:27:48",
                "fault_type1": "阻抗异常",
                "log_path": "SN-MODEL/stress.log",
            }
        ]
        mes = AsyncMock()
        mes.get_server = AsyncMock(
            return_value=ServerInfo(
                server_sn="SN-MODEL",
                model="",
                product_models="Model-X1,Model-X2",
            )
        )
        mes.get_test_details = AsyncMock(
            return_value={"items": raw_logs, "total": 1}
        )
        mes.__aenter__ = AsyncMock(return_value=mes)
        mes.__aexit__ = AsyncMock(return_value=None)

        registry = Mock()
        machine_prompt = {
            "model": "Model-X1",
            "system_prompt": "model-x1-system",
            "user_template": "model-x1-log={log_text}",
        }
        registry.get_prompt = AsyncMock(return_value=machine_prompt)
        download_logs = AsyncMock(return_value=("", []))
        progress_events: list[tuple[str, dict]] = []

        async def capture_progress(
            stage: str,
            _detail: str,
            _status: str,
            metadata: Optional[dict],
        ) -> None:
            progress_events.append((stage, metadata or {}))

        with _factory_mock(), patch(
            "app.routers.diagnosis.MESDirectService", return_value=mes
        ), patch("app.routers.diagnosis.knowledge_graph") as mock_kg, patch(
            "app.routers.diagnosis.PromptRegistry", return_value=registry
        ), patch(
            "app.routers.diagnosis._download_failed_item_logs", new=download_logs
        ), patch.object(
            diagnosis_router.ragflow_service,
            "search_knowledge_base",
            new=AsyncMock(return_value={"references": []}),
        ):
            mock_kg.get_device_by_sn = AsyncMock(
                return_value={"id": "device-1", "sn": "SN-MODEL", "model": ""}
            )
            mock_kg.get_device_test_logs = AsyncMock(return_value=[])
            mock_kg.get_device_maintenance_history = AsyncMock(return_value=[])
            mock_kg.find_similar_cases = AsyncMock(return_value=[])

            result = await diagnosis_router._gather_sn_data(
                "SN-MODEL", "Factory-A", on_progress=capture_progress
            )

        assert result[0]["model"] == "Model-X1"
        registry.get_prompt.assert_awaited_once_with("Model-X1")
        assert download_logs.await_args.kwargs["machine_model"] == "Model-X1"
        assert download_logs.await_args.kwargs["extraction_prompt"] == machine_prompt
        prompt_metadata = [meta for stage, meta in progress_events if stage == "prompt"][-1]
        assert prompt_metadata == {
            "machine_model": "Model-X1",
            "prompt_model": "Model-X1",
            "system_prompt": "model-x1-system",
            "user_template": "model-x1-log={log_text}",
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("items", "expected_reason", "expected_llm_log_count"),
        [
            (
                [{"server_test_result": "成功", "detailed_flow": "Stress Check"}],
                "未发现失败测试项",
                0,
            ),
            (
                [{"server_test_result": "失败", "detailed_flow": "Stress Check"}],
                "均未提供日志路径",
                1,
            ),
        ],
    )
    async def test_gather_reports_skipped_log_extraction_stages(
        self,
        items: list[dict],
        expected_reason: str,
        expected_llm_log_count: int,
    ):
        """无可用失败日志时应明确报告四个 AI 日志阶段已跳过。"""
        progress_events: list[tuple[str, str, str]] = []

        async def capture_progress(
            stage: str, detail: str, status: str, _metadata: Optional[dict]
        ) -> None:
            progress_events.append((stage, detail, status))

        download_logs = AsyncMock(return_value=("", []))
        with _factory_mock(), _mes_mock(items=items), _prompt_mock(), patch(
            "app.routers.diagnosis.knowledge_graph"
        ) as mock_kg, patch(
            "app.routers.diagnosis._download_failed_item_logs", new=download_logs
        ), patch.object(
            diagnosis_router.ragflow_service,
            "search_knowledge_base",
            new=AsyncMock(return_value={"references": []}),
        ):
            mock_kg.get_device_by_sn = AsyncMock(
                return_value={"id": "device-1", "sn": "SN-SKIP", "model": "X1"}
            )
            mock_kg.get_device_test_logs = AsyncMock(return_value=[])
            mock_kg.get_device_maintenance_history = AsyncMock(return_value=[])
            mock_kg.find_similar_cases = AsyncMock(return_value=[])

            result = await diagnosis_router._gather_sn_data(
                "SN-SKIP", "Factory-A", on_progress=capture_progress
            )

        log_events = [event for event in progress_events if event[0].startswith("log_")]
        assert [event[0] for event in log_events] == [
            "log_download",
            "log_split",
            "log_extract",
            "log_merge",
        ]
        assert all(event[2] == "skipped" for event in log_events)
        assert expected_reason in log_events[0][1]
        assert len(result[1]) == expected_llm_log_count

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

        with _factory_mock(), _mes_mock(), _prompt_mock():
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

        with _factory_mock(), _mes_mock(items=[]), _prompt_mock():
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

    @pytest.mark.asyncio
    async def test_diagnose_sn_streams_progress_and_merged_log(
        self, async_client, auth_headers: dict, sample_diagnosis_result: dict
    ):
        async def fake_gather(_sn, _factory, on_progress=None):
            await on_progress("log_split", "日志共 501 行，已拆分为 2 块")
            await on_progress("log_extract", "已完成 2/2 个日志块")
            return (
                {"id": "device-1", "sn": "SN123", "model": "X1"},
                [],
                [],
                [],
                [],
                "## 聚合错误日志\nERROR disk offline",
                [],
                [],
                "# SN SN123 聚合错误日志\nERROR disk offline\n",
            )

        with patch(
            "app.routers.diagnosis._gather_sn_data", new=AsyncMock(side_effect=fake_gather)
        ), patch("app.routers.diagnosis.llm_service") as mock_llm:
            mock_llm.diagnose_sn = AsyncMock(return_value=sample_diagnosis_result)
            response = await async_client.post(
                "/api/diagnosis/sn/analyze",
                headers=auth_headers,
                json={"sn": "SN123", "factory": "Factory-A"},
            )

        assert response.status_code == 200
        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        assert [event["stage"] for event in events if event["type"] == "progress"][:2] == [
            "log_split",
            "log_extract",
        ]
        assert all(
            event["status"] == "running"
            for event in events
            if event["type"] == "progress"
        )
        result = next(event["data"] for event in events if event["type"] == "result")
        assert "ERROR disk offline" in result["merged_error_log"]

    @pytest.mark.asyncio
    async def test_diagnose_sn_stream_returns_parse_error_details(
        self, async_client, auth_headers: dict
    ):
        async def fake_gather(_sn, _factory, on_progress=None):
            await on_progress("ragflow", "知识库检索完成")
            return ({}, [], [], [], [], "", [], [], "")

        parse_error = LLMResponseParseError(
            "invalid response with api_key=secret-value",
            "Expecting value: line 1 column 1",
        )
        with patch(
            "app.routers.diagnosis._gather_sn_data", new=AsyncMock(side_effect=fake_gather)
        ), patch("app.routers.diagnosis.llm_service") as mock_llm:
            mock_llm.diagnose_sn = AsyncMock(side_effect=parse_error)
            response = await async_client.post(
                "/api/diagnosis/sn/analyze",
                headers=auth_headers,
                json={"sn": "SN123", "factory": "Factory-A"},
            )

        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        error = next(event for event in events if event["type"] == "error")
        assert error["error_code"] == "LLM_RESPONSE_PARSE_ERROR"
        assert error["stage"] == "llm"
        assert "invalid response" in error["error_detail"]
        assert "secret-value" not in error["error_detail"]


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

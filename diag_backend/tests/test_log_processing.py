"""
log_processing 包单元测试 — 分段、并发提取扁平化、未配置 AI 时的编码级回退。

这些测试不依赖 MongoDB：PromptRegistry.get_prompt 与 llm_service._ensure_configured
均被 mock，从而覆盖 process_log 的两条主路径。
"""
import asyncio
import inspect
from typing import ClassVar
from unittest.mock import AsyncMock, patch

import pytest

from app.services.log_processing import (
    AILogExtractor,
    LogSegmenter,
    preprocess_log,
    process_log,
)
from app.services.log_processing.segmenter import LogSegment
from app.services.log_processing.ai_extractor import llm_service as ae_llm
from app.services.log_processing import llm_service as lp_llm
from app.services.log_processing.prompt_registry import DEFAULT_ID


@pytest.fixture(autouse=True)
def _mock_runtime_config(monkeypatch):
    """隔离运行时配置：process_log 的并发解析不依赖真实 MongoDB。"""
    from app.services.runtime_config_service import runtime_config_service

    async def fake_get():
        return {"per_request_concurrency": 8, "global_concurrency": 16}

    monkeypatch.setattr(runtime_config_service, "get", fake_get)
    yield


def _make_text(lines: int, per_line: int = 10) -> str:
    return "".join(f"line{i:0{per_line}d} content\n" for i in range(lines))


class TestLogSegmenter:
    def test_basic_split(self):
        text = _make_text(300)  # 300 行
        segs = LogSegmenter.split(text, max_chars=1000, overlap=0)
        assert len(segs) >= 3
        # 拼接回去看是否覆盖了原文（去换行误差）
        joined = "".join(segs)
        assert "line0000000000" in joined and "line0000000299" in joined

    def test_overlap_increases_segments(self):
        text = _make_text(300)
        no_overlap = LogSegmenter.split(text, max_chars=1000, overlap=0)
        with_overlap = LogSegmenter.split(text, max_chars=1000, overlap=50)
        assert len(with_overlap) > len(no_overlap)

    def test_single_small_segment(self):
        text = "short log\nsecond line\n"
        segs = LogSegmenter.split(text, max_chars=10000, overlap=0)
        assert len(segs) == 1
        assert segs[0] == text

    def test_source_line_numbers_are_retained(self):
        segments = LogSegmenter.split_with_metadata(
            "ERROR one\nWARN two\n",
            max_chars=1000,
            overlap=0,
            source_line_numbers=(101, 205),
        )

        assert segments[0].start_line == 101
        assert segments[0].end_line == 205
        assert segments[0].source_line_numbers == (101, 205)

    def test_oversized_single_line_is_split_with_offsets(self):
        text = ("x" * 250) + "\n"

        segments = LogSegmenter.split_with_metadata(text, max_chars=100, overlap=0)

        assert "".join(segment.text for segment in segments) == text
        assert all(len(segment.text) <= 100 for segment in segments)
        assert [segment.start_line for segment in segments] == [1, 1, 1]
        assert [segment.source_char_offsets[0] for segment in segments] == [0, 100, 200]


class TestLogPreprocessor:
    def test_filters_normal_info_debug_case_insensitively(self):
        result = preprocess_log(
            "INFO boot ok\n"
            "debug cache hit\n"
            "Info test FAILED\n"
            "failure context continuation\n"
            "warning temperature high\n"
            "ERROR disk offline\n",
            context_before=0,
            context_after=0,
            min_level_markers=1,
        )

        assert result.applied is True
        assert result.source_line_numbers == (3, 4, 5, 6)
        assert "boot ok" not in result.text
        assert "cache hit" not in result.text
        assert "test FAILED" in result.text
        assert "temperature high" in result.text
        assert "disk offline" in result.text

    def test_keeps_context_around_anomaly(self):
        lines = [f"INFO routine {index}\n" for index in range(1, 31)]
        lines[15] = "ERROR fan failed\n"

        result = preprocess_log(
            "".join(lines),
            context_before=2,
            context_after=3,
            min_level_markers=1,
        )

        assert result.source_line_numbers == tuple(range(14, 20))
        assert "[L16] ERROR fan failed" in result.text

    def test_unrecognized_format_is_not_cleaned(self):
        raw_text = "startup complete\ncustom status line\ndisk looks healthy\n"

        result = preprocess_log(raw_text)

        assert result.applied is False
        assert result.text == raw_text
        assert result.removed_lines == 0

    def test_level_marker_late_in_message_does_not_start_new_entry(self):
        raw_text = (
            "INFO startup ok\n"
            + "continuation "
            + ("x" * 180)
            + " DEBUG is only message text\n"
            + "INFO service ready\n"
            + "INFO shutdown ok\n"
        )

        result = preprocess_log(
            raw_text,
            context_before=0,
            context_after=0,
            min_level_markers=1,
        )

        assert result.recognized_level_lines == 3
        assert result.kept_lines == 0

    def test_structured_logger_ignores_benign_error_fields_in_command_output(self):
        raw_text = (
            "2026-07-23 10:00:00 - health.Check - INFO - output follows\n"
            "Critical Warning: 0x00\n"
            "Error Information Log Entries: 0\n"
            "No Errors Logged\n"
            "Warning Temperature Threshold: 77 Celsius\n"
            "2026-07-23 10:00:01 - health.Check - INFO - check item Timeout Abort\n"
            "2026-07-23 10:00:02 - health.Check - INFO - all checks passed\n"
        )

        result = preprocess_log(
            raw_text,
            context_before=0,
            context_after=0,
            min_level_markers=1,
        )

        assert result.recognized_level_lines == 3
        assert result.anomaly_entries == 0
        assert result.kept_lines == 0

    def test_large_multiline_output_keeps_local_context_not_entire_entry(self):
        lines = ["2026-07-23 10:00:00 - test.Check - INFO - output follows\n"]
        lines.extend(f"device field {index}: ok\n" for index in range(100))
        lines.append("kernel: failed to assign BAR resource\n")
        lines.extend(f"device tail {index}: ok\n" for index in range(100))
        lines.extend(
            [
                "2026-07-23 10:00:01 - test.Check - INFO - cleanup\n",
                "2026-07-23 10:00:02 - test.Check - INFO - done\n",
            ]
        )

        result = preprocess_log(
            "".join(lines),
            context_before=2,
            context_after=3,
            min_level_markers=1,
        )

        assert result.source_line_numbers == tuple(range(100, 106))
        assert "failed to assign BAR resource" in result.text
        assert result.kept_lines == 6

    def test_strong_failure_overrides_benign_check_item_text(self):
        result = preprocess_log(
            "INFO boot ok\n"
            "INFO check item failed because threshold exceeded\n"
            "INFO shutdown ok\n",
            context_before=0,
            context_after=0,
            min_level_markers=1,
        )

        assert result.source_line_numbers == (2,)
        assert "failed because threshold exceeded" in result.text

    def test_unknown_format_uses_strong_anchor_instead_of_full_log(self):
        lines = [f"custom routine {index}\n" for index in range(100)]
        lines[50] = "device offline after link reset\n"

        result = preprocess_log(
            "".join(lines),
            context_before=1,
            context_after=1,
        )

        assert result.applied is True
        assert result.source_line_numbers == (50, 51, 52)
        assert result.kept_lines == 3


class TestAILogExtractor:
    def test_concurrency_default_resolved_from_runtime_config(self):
        # 默认参数为 None：由运行时配置 per_request_concurrency 解析（兜底 8）
        assert inspect.signature(process_log).parameters["concurrency"].default is None
        assert AILogExtractor().concurrency == 8

    def test_flatten_structured(self):
        structured = {
            "errors": [
                {"severity": "ERROR", "line_number": 12, "line_content": "fan failed",
                 "analysis": "cooling issue"},
                {"severity": "WARN", "line_number": 20, "line_content": "temp high"},
            ],
            "summary": "detected cooling anomalies",
            "has_critical_errors": False,
            "suggested_root_cause": "fan malfunction",
        }
        flat = AILogExtractor._flatten(structured)
        assert "共 2 个错误点" in flat
        assert "fan failed" in flat
        assert "cooling issue" in flat
        assert "detected cooling anomalies" in flat
        assert "fan malfunction" in flat

    def test_flatten_empty(self):
        flat = AILogExtractor._flatten({"errors": [], "summary": "", "has_critical_errors": False,
                                        "suggested_root_cause": ""})
        assert "共 0 个错误点" in flat

    def test_maps_cleaned_relative_line_to_original_line(self):
        segment = LogSegment(
            "[L101] ERROR fan failed\n[L205] WARN retry\n",
            101,
            205,
            0,
            (101, 205),
        )

        assert AILogExtractor._global_line_number(1, segment) == 101
        assert AILogExtractor._global_line_number(205, segment) == 205


class TestProcessLog:
    @pytest.mark.asyncio
    async def test_uses_runtime_config_concurrency(self):
        """未显式传 concurrency 时读取运行时配置 per_request_concurrency。"""
        from app.services.runtime_config_service import runtime_config_service

        fake_result = {
            "errors": [], "summary": "ok", "has_critical_errors": False,
            "suggested_root_cause": "",
        }
        default_prompt = {
            "model": DEFAULT_ID,
            "system_prompt": "sys",
            "user_template": "log={log_text}",
        }

        class _SpyExtractor(AILogExtractor):
            instances: ClassVar[list] = []

            def __init__(self, concurrency: int = 8, **kwargs):
                super().__init__(concurrency=concurrency, **kwargs)
                self.instances.append(concurrency)

        with patch.object(
            lp_llm, "_ensure_configured", new=AsyncMock()
        ), patch.object(
            __import__("app.services.log_processing.prompt_registry", fromlist=["PromptRegistry"]).PromptRegistry,
            "get_prompt",
            new=AsyncMock(return_value=default_prompt),
        ), patch.object(
            ae_llm, "extract_log_with_llm", new=AsyncMock(return_value=fake_result)
        ), patch.object(
            runtime_config_service, "get",
            new=AsyncMock(return_value={"per_request_concurrency": 4, "global_concurrency": 16}),
        ), patch(
            "app.services.log_processing.AILogExtractor", _SpyExtractor
        ):
            await process_log("ERROR x\n" * 120, segment_chars=60)

        assert _SpyExtractor.instances[-1] == 4

    @pytest.mark.asyncio
    async def test_fallback_when_ai_unavailable(self):
        """AI 未配置时回退编码级提取且 ai_extracted=False"""
        default_prompt = {
            "model": DEFAULT_ID,
            "system_prompt": "sys",
            "user_template": "log={log_text}",
        }
        with patch.object(
            __import__("app.services.log_processing.prompt_registry", fromlist=["PromptRegistry"]).PromptRegistry,
            "get_prompt",
            new=AsyncMock(return_value=default_prompt),
        ), patch.object(
            lp_llm, "_ensure_configured",
            new=AsyncMock(side_effect=RuntimeError("AI 配置未初始化")),
        ):
            result = await process_log("ERROR: disk offline\nWARN: retry\nINFO: ok", machine_model="X1")

        assert result["stats"]["ai_extracted"] is False
        assert result["stats"]["prompt_model"] == DEFAULT_ID
        # 编码级提取应保留原始错误行
        assert "disk offline" in result["extracted"]
        assert result["structured"] is None

    @pytest.mark.asyncio
    async def test_uses_pre_resolved_machine_prompt(self):
        """主流程已解析 Prompt 时直接复用，不再重复查询注册表。"""
        machine_prompt = {
            "model": "Model-X1",
            "system_prompt": "model-x1-system",
            "user_template": "model-x1-log={log_text}",
        }
        structured = {
            "errors": [],
            "summary": "ok",
            "has_critical_errors": False,
            "suggested_root_cause": "",
        }
        get_prompt = AsyncMock()
        extract = AsyncMock(return_value=(structured, "extracted"))

        with patch(
            "app.services.log_processing.PromptRegistry.get_prompt",
            new=get_prompt,
        ), patch.object(
            lp_llm, "_ensure_configured", new=AsyncMock(return_value=None)
        ), patch(
            "app.services.log_processing.AILogExtractor.extract",
            new=extract,
        ):
            result = await process_log(
                "ERROR disk offline\n",
                machine_model="Model-X1",
                prompt_config=machine_prompt,
            )

        get_prompt.assert_not_awaited()
        assert extract.await_args.args[1] == "model-x1-system"
        assert extract.await_args.args[2] == "model-x1-log={log_text}"
        assert result["stats"]["model_used"] == "Model-X1"
        assert result["stats"]["prompt_model"] == "Model-X1"

    @pytest.mark.asyncio
    async def test_segments_when_ai_ready(self):
        """AI 可用时应分段并调用并发提取（mock），返回结构化结果"""
        default_prompt = {
            "model": DEFAULT_ID,
            "system_prompt": "sys",
            "user_template": "log={log_text}",
        }

        async def fake_extract(
            seg,
            encoding_stats=None,
            system_prompt=None,
            user_template=None,
            client="extraction",
            raise_on_error=False,
        ):
            return {
                "errors": [{"severity": "ERROR", "line_number": 1, "line_content": seg[:20]}],
                "summary": "ok",
                "has_critical_errors": False,
                "suggested_root_cause": "",
            }

        with patch.object(
            __import__("app.services.log_processing.prompt_registry", fromlist=["PromptRegistry"]).PromptRegistry,
            "get_prompt",
            new=AsyncMock(return_value=default_prompt),
        ), patch.object(
            lp_llm, "_ensure_configured", new=AsyncMock(return_value=None),
        ), patch.object(
            lp_llm, "_config",
            {"answer": {"api_key": "sk"}, "extraction": {"api_key": "sk", "model": "mini"}},
            create=True,
        ), patch.object(
            ae_llm, "extract_log_with_llm", new=AsyncMock(side_effect=fake_extract),
        ):
            text = _make_text(500)
            result = await process_log(text, machine_model="X1", segment_chars=1000, concurrency=4)

        assert result["stats"]["ai_extracted"] is True
        assert result["stats"]["segment_count"] >= 1
        assert result["structured"] is not None
        assert len(result["structured"]["errors"]) >= 1
        assert "ok" in result["extracted"]

    @pytest.mark.asyncio
    async def test_500_lines_over_character_budget_are_chunked(self):
        default_prompt = {"model": DEFAULT_ID, "system_prompt": "sys", "user_template": "{log_text}"}
        fake_result = {
            "errors": [], "summary": "ok", "has_critical_errors": False,
            "suggested_root_cause": "",
        }
        with patch(
            "app.services.log_processing.PromptRegistry.get_prompt",
            new=AsyncMock(return_value=default_prompt),
        ), patch.object(lp_llm, "_ensure_configured", new=AsyncMock(return_value=None)), patch.object(
            ae_llm, "extract_log_with_llm", new=AsyncMock(return_value=fake_result)
        ):
            result = await process_log(_make_text(500), segment_chars=100)

        assert result["stats"]["processing_mode"] == "chunked"
        assert result["stats"]["segment_count"] > 1

    @pytest.mark.asyncio
    async def test_more_than_500_lines_are_chunked(self):
        default_prompt = {"model": DEFAULT_ID, "system_prompt": "sys", "user_template": "{log_text}"}
        fake_result = {
            "errors": [], "summary": "ok", "has_critical_errors": False,
            "suggested_root_cause": "",
        }
        with patch(
            "app.services.log_processing.PromptRegistry.get_prompt",
            new=AsyncMock(return_value=default_prompt),
        ), patch.object(lp_llm, "_ensure_configured", new=AsyncMock(return_value=None)), patch.object(
            ae_llm, "extract_log_with_llm", new=AsyncMock(return_value=fake_result)
        ):
            result = await process_log(_make_text(501), segment_chars=1000, overlap=0)

        assert result["stats"]["processing_mode"] == "chunked"
        assert result["stats"]["segment_count"] > 1

    @pytest.mark.asyncio
    async def test_large_log_is_cleaned_before_ai_chunking(self):
        default_prompt = {
            "model": DEFAULT_ID,
            "system_prompt": "sys",
            "user_template": "{log_text}",
        }
        lines = [f"info routine event {index}\n" for index in range(1, 502)]
        lines[250] = "WaRnInG temperature high\n"

        async def fake_extract(segment, **_kwargs):
            assert "[L251] WaRnInG temperature high" in segment
            assert "routine event 1" not in segment
            return {
                "errors": [
                    {
                        "severity": "WARN",
                        "line_number": 251,
                        "line_content": "temperature high",
                    }
                ],
                "summary": "temperature warning",
                "has_critical_errors": False,
                "suggested_root_cause": "cooling",
            }

        with patch(
            "app.services.log_processing.PromptRegistry.get_prompt",
            new=AsyncMock(return_value=default_prompt),
        ), patch.object(
            lp_llm, "_ensure_configured", new=AsyncMock(return_value=None)
        ), patch.object(
            ae_llm, "extract_log_with_llm", new=AsyncMock(side_effect=fake_extract)
        ):
            result = await process_log("".join(lines), segment_chars=10000)

        assert result["stats"]["processing_mode"] == "prefiltered_chunked"
        assert result["stats"]["preprocessing_applied"] is True
        assert result["stats"]["preprocessing_kept_lines"] == 31
        assert result["stats"]["preprocessing_removed_lines"] == 470
        assert result["structured"]["errors"][0]["line_number"] == 251

    @pytest.mark.asyncio
    async def test_large_normal_info_log_skips_ai_extraction(self):
        default_prompt = {
            "model": DEFAULT_ID,
            "system_prompt": "sys",
            "user_template": "{log_text}",
        }
        extract = AsyncMock()
        raw_text = "".join(f"INFO routine event {index}\n" for index in range(501))

        with patch(
            "app.services.log_processing.PromptRegistry.get_prompt",
            new=AsyncMock(return_value=default_prompt),
        ), patch.object(
            lp_llm, "_ensure_configured", new=AsyncMock(return_value=None)
        ), patch(
            "app.services.log_processing.AILogExtractor.extract", new=extract
        ):
            result = await process_log(raw_text)

        extract.assert_not_awaited()
        assert result["stats"]["processing_mode"] == "prefiltered_empty"
        assert result["stats"]["error_count"] == 0
        assert result["stats"]["preprocessing_removed_lines"] == 501

    @pytest.mark.asyncio
    async def test_partial_chunk_failure_keeps_successful_results(self):
        default_prompt = {"model": DEFAULT_ID, "system_prompt": "sys", "user_template": "{log_text}"}

        async def fake_extract(_seg, encoding_stats=None, **_kwargs):
            if encoding_stats["segment_index"] == 0:
                raise RuntimeError("first chunk failed")
            return {
                "errors": [{"severity": "ERROR", "line_number": 1, "line_content": "disk failed"}],
                "summary": "ok", "has_critical_errors": False, "suggested_root_cause": "disk",
            }

        with patch(
            "app.services.log_processing.PromptRegistry.get_prompt",
            new=AsyncMock(return_value=default_prompt),
        ), patch.object(lp_llm, "_ensure_configured", new=AsyncMock(return_value=None)), patch.object(
            ae_llm, "extract_log_with_llm", new=AsyncMock(side_effect=fake_extract)
        ):
            result = await process_log(_make_text(501), segment_chars=1000, overlap=0)

        assert result["stats"]["ai_extracted"] is True
        assert result["stats"]["failed_segments"] == 1
        assert result["stats"]["successful_segments"] >= 1
        assert "disk failed" in result["extracted"]
        assert "编码级补偿" in result["extracted"]

    @pytest.mark.asyncio
    async def test_all_chunk_failures_use_regex_fallback(self):
        default_prompt = {"model": DEFAULT_ID, "system_prompt": "sys", "user_template": "{log_text}"}
        with patch(
            "app.services.log_processing.PromptRegistry.get_prompt",
            new=AsyncMock(return_value=default_prompt),
        ), patch.object(lp_llm, "_ensure_configured", new=AsyncMock(return_value=None)), patch.object(
            ae_llm,
            "extract_log_with_llm",
            new=AsyncMock(side_effect=RuntimeError("model unavailable")),
        ):
            result = await process_log("INFO boot\nERROR disk offline\n", segment_chars=100)

        assert result["stats"]["ai_extracted"] is False
        assert result["stats"]["processing_mode"] == "regex_fallback"
        assert "disk offline" in result["extracted"]

    @pytest.mark.asyncio
    async def test_aggregates_global_line_numbers_and_occurrences(self):
        segments = [
            LogSegment("ERROR fan failed\n", 101, 101, 0),
            LogSegment("ERROR fan failed\n", 205, 205, 1),
        ]
        fake_result = {
            "errors": [{"severity": "ERROR", "line_number": 1, "line_content": "fan failed"}],
            "summary": "fan", "has_critical_errors": False, "suggested_root_cause": "fan",
        }
        with patch.object(
            ae_llm, "extract_log_with_llm", new=AsyncMock(return_value=fake_result)
        ):
            structured, flattened = await AILogExtractor().extract(segments, "sys", "{log_text}")

        error = structured["errors"][0]
        assert error["line_numbers"] == [101, 205]
        assert error["occurrence_count"] == 2
        assert "重复出现: 2 次" in flattened

    @pytest.mark.asyncio
    async def test_global_concurrency_is_capped_across_extractors(self):
        active = 0
        peak = 0

        async def fake_extract(_segment, **_kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return {
                "errors": [], "summary": "ok", "has_critical_errors": False,
                "suggested_root_cause": "",
            }

        segments = [LogSegment(f"ERROR {index}\n", index + 1, index + 1, index) for index in range(16)]
        with patch.object(ae_llm, "extract_log_with_llm", new=AsyncMock(side_effect=fake_extract)):
            await asyncio.gather(
                AILogExtractor().extract(segments, "sys", "{log_text}"),
                AILogExtractor().extract(segments, "sys", "{log_text}"),
                AILogExtractor().extract(segments, "sys", "{log_text}"),
            )

        assert peak == 16

    @pytest.mark.asyncio
    async def test_validates_and_normalizes_ai_payload_before_deduplication(self):
        segments = [
            LogSegment("ERROR fan failed\n", 1, 1, 0),
            LogSegment("ERROR fan failed\n", 2, 2, 1),
        ]
        responses = [
            {
                "errors": [
                    {
                        "severity": "error",
                        "line_number": 1,
                        "line_content": "2026-07-23 10:00:00 Fan   failed",
                        "component": "FAN1",
                    },
                    "invalid item",
                ],
                "summary": "fan issue",
                "has_critical_errors": False,
                "suggested_root_cause": "fan",
            },
            {
                "errors": [
                    {
                        "severity": "ERROR",
                        "line_number": 1,
                        "line_content": "2026-07-23 10:00:01 fan failed",
                        "component": "fan1",
                    }
                ],
                "summary": "fan issue",
                "has_critical_errors": False,
                "suggested_root_cause": "fan",
            },
        ]

        with patch.object(
            ae_llm,
            "extract_log_with_llm",
            new=AsyncMock(side_effect=responses),
        ):
            structured, _ = await AILogExtractor().extract(segments, "sys", "{log_text}")

        assert len(structured["errors"]) == 1
        assert structured["errors"][0]["severity"] == "ERROR"
        assert structured["errors"][0]["line_numbers"] == [1, 2]
        assert structured["summary"] == "fan issue"

    @pytest.mark.asyncio
    async def test_retries_rate_limit_and_reports_telemetry(self):
        success = {
            "errors": [], "summary": "ok", "has_critical_errors": False,
            "suggested_root_cause": "",
        }
        with patch.object(
            ae_llm,
            "extract_log_with_llm",
            new=AsyncMock(side_effect=[RuntimeError("HTTP 429"), success]),
        ), patch("app.services.log_processing.ai_extractor.asyncio.sleep", new=AsyncMock()) as sleep:
            structured, _ = await AILogExtractor().extract(
                [LogSegment("ERROR throttled\n", 1, 1, 0)],
                "sys",
                "{log_text}",
            )

        sleep.assert_awaited_once_with(0.5)
        assert structured["retry_count"] == 1

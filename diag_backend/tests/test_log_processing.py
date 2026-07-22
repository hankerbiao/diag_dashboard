"""
log_processing 包单元测试 — 分段、并发提取扁平化、未配置 AI 时的编码级回退。

这些测试不依赖 MongoDB：PromptRegistry.get_prompt 与 llm_service._ensure_configured
均被 mock，从而覆盖 process_log 的两条主路径。
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.log_processing import LogSegmenter, AILogExtractor, process_log
from app.services.log_processing.segmenter import LogSegment
from app.services.log_processing.ai_extractor import llm_service as ae_llm
from app.services.log_processing import llm_service as lp_llm
from app.services.log_processing.prompt_registry import DEFAULT_ID


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


class TestAILogExtractor:
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


class TestProcessLog:
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
    async def test_500_lines_are_sent_as_one_chunk(self):
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

        assert result["stats"]["processing_mode"] == "single"
        assert result["stats"]["segment_count"] == 1

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

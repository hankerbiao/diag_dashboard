"""
AI 并发提取器 — 对每个日志段落并发调用「快速提取模型」，聚合结构化错误。

- 用 asyncio.Semaphore 限制并发数，避免一次性打满模型限流。
- 每个段落独立调用 llm_service.extract_log_with_llm（使用按机型配置的 prompt）。
- 聚合各段 errors，按行内容去重，拼接 summary。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from weakref import WeakKeyDictionary
from typing import Awaitable, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..llm_service import llm_service
from ..log_extractor import extract_log_context
from .segmenter import LogSegment

logger = logging.getLogger(__name__)

GLOBAL_EXTRACTION_CONCURRENCY = 16
MAX_AGGREGATED_ERRORS = 500
_GLOBAL_SEMAPHORES: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    WeakKeyDictionary()
)


def _global_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    semaphore = _GLOBAL_SEMAPHORES.get(loop)
    if semaphore is None:
        semaphore = asyncio.Semaphore(GLOBAL_EXTRACTION_CONCURRENCY)
        _GLOBAL_SEMAPHORES[loop] = semaphore
    return semaphore


class _AIError(BaseModel):
    model_config = ConfigDict(extra="allow")

    severity: str = "ERROR"
    line_number: int | str | None = None
    line_content: str = ""
    component: str = ""
    device: str = ""
    timestamp: str = ""
    context_before: str | list[str] | None = None
    context_after: str | list[str] | None = None
    analysis: str = ""

    @field_validator("severity", "component", "device", "timestamp", mode="before")
    @classmethod
    def _short_text(cls, value: object) -> str:
        return str(value or "").strip()[:256]

    @field_validator("line_content", "analysis", mode="before")
    @classmethod
    def _bounded_text(cls, value: object) -> str:
        return str(value or "").strip()[:4000]


class _AIExtractionPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    errors: list[object] = Field(default_factory=list)
    summary: str = ""
    has_critical_errors: bool = False
    suggested_root_cause: str = ""

    @field_validator("summary", "suggested_root_cause", mode="before")
    @classmethod
    def _bounded_text(cls, value: object) -> str:
        return str(value or "").strip()[:4000]

    @field_validator("errors", mode="before")
    @classmethod
    def _bounded_errors(cls, value: object) -> list[object]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("errors 必须是列表")
        return value[:MAX_AGGREGATED_ERRORS]


def _validated_payload(value: object) -> dict:
    payload = _AIExtractionPayload.model_validate(value)
    errors: list[dict] = []
    for raw_error in payload.errors:
        try:
            error = _AIError.model_validate(raw_error)
        except Exception as exc:  # noqa: BLE001
            logger.debug("忽略无效的 AI 错误项: %s", exc)
            continue
        if error.line_content:
            normalized = error.model_dump(exclude_none=True)
            normalized["severity"] = error.severity.upper() or "ERROR"
            errors.append(normalized)
    result = payload.model_dump(exclude={"errors"})
    result["errors"] = errors
    return result


_LEADING_TIMESTAMP = re.compile(
    r"^\s*(?:\[)?\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:\])?\s*"
)


def _fingerprint(error: dict) -> str:
    severity = str(error.get("severity", "ERROR")).strip().upper()
    component = str(error.get("component") or error.get("device") or "").strip().casefold()
    content = _LEADING_TIMESTAMP.sub("", str(error.get("line_content", "")))
    content = " ".join(content.split()).casefold()
    return "|".join((severity, component, content))


class AILogExtractor:
    """并发提取日志段落中的错误内容。"""

    def __init__(self, concurrency: int = 8):
        self.concurrency = max(1, concurrency)
        self.semaphore = asyncio.Semaphore(self.concurrency)

    async def extract(
        self,
        segments: list[LogSegment],
        system_prompt: str,
        user_template: str,
        client: str = "extraction",
        on_progress: Optional[Callable[[int, int], Awaitable[None]]] = None,
    ) -> tuple[dict, str]:
        """
        并发提取所有段落并聚合。

        Args:
            segments: 日志段落列表
            system_prompt: 系统提示词（按机型配置）
            user_template: 用户提示词模板（含 {log_text} 等占位符）
            client: 使用的模型客户端（"extraction" 快速模型）

        Returns:
            (structured_dict, flattened_text)
            structured_dict: {"errors":[...], "summary":str, "has_critical_errors":bool,
                              "suggested_root_cause":str}

        Raises:
            RuntimeError: 若所有段落提取均失败（供调用方回退编码级提取）
        """
        if not segments:
            return {"errors": [], "summary": "", "has_critical_errors": False,
                    "suggested_root_cause": ""}, ""

        retry_count = 0

        async def _extract_one(
            segment: LogSegment,
        ) -> tuple[LogSegment, Optional[dict], Optional[Exception]]:
            nonlocal retry_count
            async with self.semaphore:
                last_error: Optional[Exception] = None
                for attempt in range(3):
                    try:
                        async with _global_semaphore():
                            result = await llm_service.extract_log_with_llm(
                                segment.text,
                                encoding_stats={
                                    "segment_index": segment.index,
                                    "segment_count": len(segments),
                                    "segment_start_line": segment.start_line,
                                    "segment_end_line": segment.end_line,
                                    "segment_start_char_offset": (
                                        segment.source_char_offsets[0]
                                        if segment.source_char_offsets
                                        else 0
                                    ),
                                    "total_lines": (
                                        len(segment.source_line_numbers)
                                        or segment.end_line - segment.start_line + 1
                                    ),
                                    "total_chars": len(segment.text),
                                    "source_line_prefixes": bool(
                                        segment.source_line_numbers
                                        and "[L" in segment.text[:64]
                                    ),
                                },
                                system_prompt=system_prompt,
                                user_template=user_template,
                                client=client,  # type: ignore[arg-type]
                                raise_on_error=True,
                            )
                        return segment, _validated_payload(result), None
                    except Exception as exc:  # noqa: BLE001
                        last_error = exc
                        detail = str(exc).casefold()
                        retryable = bool(re.search(r"\b(?:429|500|502|503|504)\b", detail))
                        retryable = retryable or any(
                            marker in detail
                            for marker in (
                                "rate limit", "timeout", "temporarily unavailable", "connection",
                            )
                        )
                        if not retryable or attempt >= 2:
                            break
                        retry_count += 1
                        delay = 0.5 * (2**attempt)
                        logger.warning(
                            "AI 日志分块提取重试 segment=%d attempt=%d delay=%.1fs error=%s",
                            segment.index + 1,
                            attempt + 1,
                            delay,
                            exc,
                        )
                        await asyncio.sleep(delay)
                return segment, None, last_error

        results: list[tuple[LogSegment, Optional[dict], Optional[Exception]]] = []
        completed = 0

        queue: asyncio.Queue[LogSegment] = asyncio.Queue()
        for segment in segments:
            queue.put_nowait(segment)

        async def _worker() -> None:
            nonlocal completed
            while True:
                try:
                    segment = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    results.append(await _extract_one(segment))
                    completed += 1
                    if on_progress:
                        await on_progress(completed, len(segments))
                finally:
                    queue.task_done()

        tasks = [
            asyncio.create_task(_worker())
            for _ in range(min(self.concurrency, len(segments)))
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        usable = [item for item in results if item[1] is not None and item[2] is None]
        failed = [item for item in results if item[2] is not None]
        if not usable:
            first_err = failed[0][2] if failed else None
            raise RuntimeError(f"所有日志段落的 AI 提取均失败: {first_err}")
        usable.sort(key=lambda item: item[0].index)

        errors: list[dict] = []
        summaries: list[str] = []
        has_critical = False
        root_cause = ""

        for segment, r, _error in usable:
            if not isinstance(r, dict):
                continue
            for error in r.get("errors", []) or []:
                if not isinstance(error, dict):
                    continue
                normalized = dict(error)
                line_number = self._global_line_number(
                    normalized.get("line_number"), segment
                )
                normalized["line_number"] = line_number
                normalized["source_segment"] = segment.index + 1
                errors.append(normalized)
            if r.get("summary"):
                summaries.append(str(r.get("summary")))
            if r.get("has_critical_errors"):
                has_critical = True
            if r.get("suggested_root_cause"):
                root_cause = str(r.get("suggested_root_cause"))

        # Merge repeated errors while retaining occurrence count and locations.
        deduped: dict[str, dict] = {}
        for e in errors:
            if not isinstance(e, dict):
                continue
            key = _fingerprint(e) or json.dumps(e, ensure_ascii=False)
            line_number = e.get("line_number")
            if key not in deduped:
                item = dict(e)
                item["line_numbers"] = [line_number] if line_number else []
                item["occurrence_count"] = 1
                deduped[key] = item
            elif line_number and line_number not in deduped[key]["line_numbers"]:
                deduped[key]["line_numbers"].append(line_number)
                deduped[key]["occurrence_count"] = len(deduped[key]["line_numbers"])

        unique_summaries = list(dict.fromkeys(summary for summary in summaries if summary))
        root_causes = list(
            dict.fromkeys(
                str(item[1].get("suggested_root_cause", "")).strip()
                for item in usable
                if item[1] and item[1].get("suggested_root_cause")
            )
        )
        structured = {
            "errors": list(deduped.values()),
            "summary": "\n".join(unique_summaries)[:8000],
            "has_critical_errors": has_critical,
            "suggested_root_cause": "；".join(root_causes)[:4000] or root_cause,
            "successful_segments": len(usable),
            "failed_segments": len(failed),
            "total_segments": len(segments),
            "fallback_matched_lines": 0,
            "retry_count": retry_count,
        }
        flattened = self._flatten(structured)
        if failed:
            fallback_parts: list[str] = []
            fallback_matched_lines = 0
            for segment, _result, _error in sorted(failed, key=lambda item: item[0].index):
                fallback_text, fallback_stats = extract_log_context(segment.text, mode="balanced")
                fallback_matched_lines += fallback_stats.get("matched_lines", 0)
                fallback_parts.append(
                    f"[编码级补偿 - 原日志第 {segment.start_line}-{segment.end_line} 行]\n"
                    f"{fallback_text}"
                )
            structured["fallback_matched_lines"] = fallback_matched_lines
            flattened = f"{flattened}\n\n" + "\n\n".join(fallback_parts)
        return structured, flattened

    @staticmethod
    def _global_line_number(value: object, segment: LogSegment) -> int | str:
        try:
            line_number = int(value)
        except (TypeError, ValueError):
            return value if isinstance(value, str) else segment.start_line
        if segment.source_line_numbers:
            if line_number in segment.source_line_numbers:
                return line_number
            if 1 <= line_number <= len(segment.source_line_numbers):
                return segment.source_line_numbers[line_number - 1]
            return line_number
        segment_lines = segment.end_line - segment.start_line + 1
        if segment.start_line <= line_number <= segment.end_line:
            return line_number
        if 1 <= line_number <= segment_lines:
            return segment.start_line + line_number - 1
        return line_number

    @staticmethod
    def _flatten(structured: dict) -> str:
        """将结构化结果转为扁平文本，兼容下游（诊断/剖析 prompt）输入形态。"""
        errors = structured.get("errors", []) or []
        lines: list[str] = [f"[AI 提取 - 共 {len(errors)} 个错误点]"]
        summary = structured.get("summary")
        if summary:
            lines.append("")
            lines.append("SUMMARY:")
            lines.append(str(summary))
        if structured.get("suggested_root_cause"):
            lines.append("")
            lines.append(f"初步根因建议: {structured.get('suggested_root_cause')}")
        if errors:
            lines.append("")
            lines.append("ERRORS:")
            for i, e in enumerate(errors, 1):
                severity = e.get("severity", "ERROR")
                line_no = e.get("line_number", "")
                content = e.get("line_content", "")
                lines.append(f"{i}. [{severity}] line {line_no}: {content}")
                if e.get("occurrence_count", 1) > 1:
                    locations = ", ".join(map(str, e.get("line_numbers", [])))
                    lines.append(
                        f"   重复出现: {e.get('occurrence_count')} 次（行 {locations}）"
                    )
                cb = e.get("context_before")
                if cb:
                    lines.append(f"   前序: {cb if isinstance(cb, str) else ' | '.join(map(str, cb))}")
                ca = e.get("context_after")
                if ca:
                    lines.append(f"   后序: {ca if isinstance(ca, str) else ' | '.join(map(str, ca))}")
                if e.get("analysis"):
                    lines.append(f"   分析: {e.get('analysis')}")
        return "\n".join(lines)

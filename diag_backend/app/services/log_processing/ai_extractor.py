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
from typing import Awaitable, Callable, Optional

from ..llm_service import llm_service
from ..log_extractor import extract_log_context
from .segmenter import LogSegment

logger = logging.getLogger(__name__)


class AILogExtractor:
    """并发提取日志段落中的错误内容。"""

    def __init__(self, concurrency: int = 6):
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

        async def _extract_one(
            segment: LogSegment,
        ) -> tuple[LogSegment, Optional[dict], Optional[Exception]]:
            async with self.semaphore:
                try:
                    result = await llm_service.extract_log_with_llm(
                        segment.text,
                        encoding_stats={
                            "segment_index": segment.index,
                            "segment_count": len(segments),
                            "segment_start_line": segment.start_line,
                            "segment_end_line": segment.end_line,
                            "total_lines": segment.end_line - segment.start_line + 1,
                            "total_chars": len(segment.text),
                        },
                        system_prompt=system_prompt,
                        user_template=user_template,
                        client=client,  # type: ignore[arg-type]
                        raise_on_error=True,
                    )
                    return segment, result, None
                except Exception as exc:  # noqa: BLE001
                    return segment, None, exc

        tasks = [asyncio.create_task(_extract_one(segment)) for segment in segments]
        results: list[tuple[LogSegment, Optional[dict], Optional[Exception]]] = []
        completed = 0
        for task in asyncio.as_completed(tasks):
            results.append(await task)
            completed += 1
            if on_progress:
                await on_progress(completed, len(segments))

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
            key = "|".join(
                [str(e.get("severity", "")), str(e.get("line_content", "")).strip()]
            ) or json.dumps(e, ensure_ascii=False)
            line_number = e.get("line_number")
            if key not in deduped:
                item = dict(e)
                item["line_numbers"] = [line_number] if line_number else []
                item["occurrence_count"] = 1
                deduped[key] = item
            elif line_number and line_number not in deduped[key]["line_numbers"]:
                deduped[key]["line_numbers"].append(line_number)
                deduped[key]["occurrence_count"] = len(deduped[key]["line_numbers"])

        structured = {
            "errors": list(deduped.values()),
            "summary": "\n".join(summaries),
            "has_critical_errors": has_critical,
            "suggested_root_cause": root_cause,
            "successful_segments": len(usable),
            "failed_segments": len(failed),
            "total_segments": len(segments),
            "fallback_matched_lines": 0,
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

"""
独立日志处理模块（log_processing）

将「原始日志 → 错误相关内容」的提取从诊断流程中独立出来，统一负责：
1. 按机型解析提取 prompt（PromptRegistry）
2. 依据提取模型上下文窗口分段（LogSegmenter）
3. 并发调用快速提取模型抽取各段错误（AILogExtractor）
4. 聚合结构化结果；AI 不可用 / 全部失败时回退编码级提取（ContextExtractor）

对外主入口：process_log()
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from ..llm_service import llm_service
from ..log_extractor import ContextExtractor, extract_log_context
from .ai_extractor import AILogExtractor
from .prompt_registry import DEFAULT_ID, PromptRegistry
from .segmenter import LogSegment, LogSegmenter

logger = logging.getLogger(__name__)

DEFAULT_SEGMENT_CHARS = 12000
SMALL_LOG_MAX_LINES = 500


def _estimate_segment_chars() -> int:
    """依据提取模型上下文窗口推算每段字符预算（约 50% 输入 + 2 字符/token）。

    配置未加载时回退默认 12000。
    """
    try:
        ctx = llm_service.get_config_value("model_context_len", client="extraction")
        if ctx and isinstance(ctx, (int, float)) and ctx > 4000:
            # 约 50% 上下文作为输入预算，按 2 字符/token 估算，并限制上限避免单段过大
            return min(24000, max(4000, int(ctx * 0.5 * 2)))
    except Exception:
        pass
    return DEFAULT_SEGMENT_CHARS


async def process_log(
    raw_text: str,
    machine_model: str = "",
    *,
    segment_chars: Optional[int] = None,
    overlap: int = 200,
    concurrency: int = 6,
    mode: str = "balanced",
    on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None,
) -> dict:
    """
    处理一段原始日志，返回 AI 提取（或编码级兜底）的结果。

    Args:
        raw_text: 原始日志全文
        machine_model: 设备机型；用于选择对应提取 prompt，空串则使用 default
        segment_chars: 每段字符预算；None 时按提取模型上下文窗口自动推算
        overlap: 段间重叠字符数
        concurrency: 并发提取段落数
        mode: 编码级兜底提取模式（light/balanced/thorough）

    Returns:
        {
          "extracted": <扁平文本，供下游诊断/剖析 prompt 使用>,
          "stats": {ai_extracted, segment_count, model_used, prompt_model, error_count, ...},
          "structured": <结构化错误 dict 或 None（编码兜底时）>,
        }
    """
    async def _progress(stage: str, detail: str) -> None:
        if on_progress:
            await on_progress(stage, detail)

    registry = PromptRegistry()
    prompt = await registry.get_prompt(machine_model)
    prompt_model = prompt.get("model", DEFAULT_ID)

    if segment_chars is None or segment_chars <= 0:
        segment_chars = _estimate_segment_chars()

    # 判断 AI 是否可用
    ai_ready = False
    try:
        await llm_service._ensure_configured()
        ai_ready = True
    except Exception as e:  # noqa: BLE001
        logger.warning("AI 未配置，回退编码级日志提取: %s", e)

    stats_base = {
        "model_used": machine_model or DEFAULT_ID,
        "prompt_model": prompt_model,
        "total_lines": len(raw_text.splitlines()) if raw_text else 0,
    }

    if not ai_ready:
        await _progress("log_merge", "提取模型不可用，正在执行编码级错误扫描")
        extracted, enc_stats = extract_log_context(raw_text, mode=mode)
        stats = {**stats_base, "ai_extracted": False, "segment_count": 0,
                 "error_count": enc_stats.get("matched_lines", 0),
                 "processing_mode": "regex_fallback", **enc_stats}
        return {"extracted": extracted, "stats": stats, "structured": None}

    # Small logs stay intact; larger logs are adaptively chunked.
    total_lines = stats_base["total_lines"]
    if total_lines <= SMALL_LOG_MAX_LINES:
        segments = [
            LogSegment(
                text=raw_text,
                start_line=1,
                end_line=total_lines,
                index=0,
            )
        ] if raw_text else []
        processing_mode = "single"
        await _progress("log_split", f"日志共 {total_lines} 行，整份交给提取模型")
    else:
        segments = LogSegmenter.split_with_metadata(raw_text, segment_chars, overlap)
        processing_mode = "chunked"
        await _progress(
            "log_split",
            f"日志共 {total_lines} 行，已自适应拆分为 {len(segments)} 块",
        )

    await _progress("log_extract", f"正在并发提取 {len(segments)} 个日志块")
    extractor = AILogExtractor(concurrency=concurrency)
    try:
        async def _chunk_progress(completed: int, total: int) -> None:
            await _progress("log_extract", f"已完成 {completed}/{total} 个日志块")

        structured, flattened = await extractor.extract(
            segments,
            prompt["system_prompt"],
            prompt["user_template"],
            on_progress=_chunk_progress,
        )
        await _progress(
            "log_merge",
            f"正在聚合 {len(structured.get('errors', []))} 个错误模式",
        )
        stats = {
            **stats_base,
            "ai_extracted": True,
            "segment_count": len(segments),
            "error_count": (
                len(structured.get("errors", []))
                + structured.get("fallback_matched_lines", 0)
            ),
            "processing_mode": processing_mode,
            "successful_segments": structured.get("successful_segments", len(segments)),
            "failed_segments": structured.get("failed_segments", 0),
        }
        return {"extracted": flattened, "stats": stats, "structured": structured}
    except Exception as e:  # noqa: BLE001
        logger.warning("AI 日志提取失败，回退编码级: %s", e)
        await _progress("log_merge", "AI 提取失败，正在执行编码级回退扫描")
        extracted, enc_stats = extract_log_context(raw_text, mode=mode)
        stats = {**stats_base, "ai_extracted": False, "segment_count": 0,
                 "error_count": enc_stats.get("matched_lines", 0),
                 "processing_mode": "regex_fallback",
                 "fallback_error": str(e), **enc_stats}
        return {"extracted": extracted, "stats": stats, "structured": None}


__all__ = [
    "process_log",
    "LogSegmenter",
    "AILogExtractor",
    "PromptRegistry",
    "ContextExtractor",
    "SMALL_LOG_MAX_LINES",
]

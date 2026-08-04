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
from time import perf_counter
from typing import Awaitable, Callable, Optional

from ..llm_service import llm_service
from ..log_extractor import ContextExtractor, extract_log_context
from .ai_extractor import AILogExtractor
from .prompt_registry import DEFAULT_ID, PromptRegistry
from .preprocessor import preprocess_log
from .segmenter import LogSegment, LogSegmenter

logger = logging.getLogger(__name__)

DEFAULT_SEGMENT_CHARS = 12000
SMALL_LOG_MAX_LINES = 500


def _estimate_segment_chars() -> int:
    """依据后端识别出的提取模型窗口推算每段字符预算。

    配置未加载时回退默认 12000。
    """
    try:
        if not llm_service.get_config_value("model", client="extraction"):
            return DEFAULT_SEGMENT_CHARS
        ctx = llm_service.get_context_window(client="extraction")
        if ctx and isinstance(ctx, (int, float)) and ctx > 4000:
            # 约 50% 上下文作为输入预算，仍限制单段大小以控制并发请求成本。
            return min(24000, max(4000, int(ctx * 0.5 * 2)))
    except Exception:
        pass
    return DEFAULT_SEGMENT_CHARS


async def process_log(
    raw_text: str,
    machine_model: str = "",
    *,
    prompt_config: Optional[dict] = None,
    segment_chars: Optional[int] = None,
    overlap: int = 200,
    concurrency: Optional[int] = None,
    mode: str = "balanced",
    on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None,
) -> dict:
    """
    处理一段原始日志，返回 AI 提取（或编码级兜底）的结果。

    Args:
        raw_text: 原始日志全文
        machine_model: 设备机型；用于选择对应提取 prompt，空串则使用 default
        prompt_config: 调用方已解析的提取 prompt；未传时按 machine_model 查询
        segment_chars: 每段字符预算；None 时按提取模型上下文窗口自动推算
        overlap: 段间重叠字符数
        concurrency: 并发提取段落数；None 时读取运行时配置
            （per_request_concurrency，设置页可实时调整）
        mode: 编码级兜底提取模式（light/balanced/thorough）

    Returns:
        {
          "extracted": <扁平文本，供下游诊断/剖析 prompt 使用>,
          "stats": {ai_extracted, segment_count, model_used, prompt_model, error_count, ...},
          "structured": <结构化错误 dict 或 None（编码兜底时）>,
        }
    """
    started_at = perf_counter()

    # 并发数：显式传参优先，否则读运行时配置（DB 不可达时回退默认 8）
    if concurrency is None:
        try:
            from ..runtime_config_service import runtime_config_service

            concurrency = (await runtime_config_service.get())["per_request_concurrency"]
        except Exception:  # noqa: BLE001
            concurrency = 8
    concurrency = max(1, int(concurrency))

    async def _progress(stage: str, detail: str) -> None:
        if on_progress:
            await on_progress(stage, detail)

    prompt = prompt_config
    if prompt is None:
        registry = PromptRegistry()
        prompt = await registry.get_prompt(machine_model)
    prompt_model = prompt.get("model", DEFAULT_ID)

    # 诊断日志：确认提取模板包含日志切片占位符，否则模型将收不到任何日志内容
    user_template = prompt.get("user_template") or ""
    if "{log_text}" not in user_template:
        logger.warning(
            "提取模板未包含 {log_text} 占位符，模型将收不到日志切片 "
            "model=%s prompt_model=%s template_preview=%.160r",
            machine_model or DEFAULT_ID,
            prompt_model,
            user_template[:160],
        )

    if segment_chars is None or segment_chars <= 0:
        segment_chars = _estimate_segment_chars()

    # 判断 AI 是否可用
    ai_ready = False
    try:
        await llm_service._ensure_configured()
        ai_ready = True
    except Exception as e:  # noqa: BLE001
        logger.warning("AI 未配置，回退编码级日志提取: %s", e)

    total_lines = len(raw_text.splitlines()) if raw_text else 0
    stats_base = {
        "model_used": machine_model or DEFAULT_ID,
        "prompt_model": prompt_model,
        "total_lines": total_lines,
        "preprocessing_applied": False,
        "preprocessing_original_lines": total_lines,
        "preprocessing_kept_lines": total_lines,
        "preprocessing_removed_lines": 0,
        "preprocessing_retention_ratio": 1.0,
        "preprocessing_level_lines": 0,
        "preprocessing_anomaly_entries": 0,
    }

    if not ai_ready:
        await _progress("log_merge", "提取模型不可用，正在执行编码级错误扫描")
        extracted, enc_stats = extract_log_context(raw_text, mode=mode)
        stats = {**stats_base, "ai_extracted": False, "segment_count": 0,
                 "error_count": enc_stats.get("matched_lines", 0),
                 "processing_mode": "regex_fallback",
                 "extraction_duration_ms": round((perf_counter() - started_at) * 1000),
                 **enc_stats}
        return {"extracted": extracted, "stats": stats, "structured": None}

    # 行数和字符数都在预算内时才整份发送，避免少量超长行撑爆模型上下文。
    is_small = total_lines <= SMALL_LOG_MAX_LINES and len(raw_text) <= segment_chars
    if is_small:
        segments = [
            LogSegment(
                text=raw_text,
                start_line=1,
                end_line=total_lines,
                index=0,
            )
        ] if raw_text else []
        processing_mode = "single"
        await _progress(
            "log_split",
            f"日志共 {total_lines} 行 / {len(raw_text)} 字符，整份交给提取模型",
        )
    else:
        preprocessed = preprocess_log(raw_text)
        stats_base.update(preprocessed.stats())
        if preprocessed.applied and not preprocessed.text:
            await _progress(
                "log_split",
                f"日志共 {total_lines} 行，规则清洗后未发现需提交 AI 的异常内容",
            )
            await _progress("log_merge", "规则清洗未发现异常，跳过 AI 分块提取")
            stats = {
                **stats_base,
                "ai_extracted": False,
                "segment_count": 0,
                "error_count": 0,
                "processing_mode": "prefiltered_empty",
                "extraction_duration_ms": round((perf_counter() - started_at) * 1000),
            }
            return {
                "extracted": "",
                "stats": stats,
                "structured": {
                    "errors": [],
                    "summary": "",
                    "has_critical_errors": False,
                    "suggested_root_cause": "",
                },
            }

        segment_text = preprocessed.text if preprocessed.applied else raw_text
        source_lines = preprocessed.source_line_numbers if preprocessed.applied else None
        segments = LogSegmenter.split_with_metadata(
            segment_text,
            segment_chars,
            overlap,
            source_line_numbers=source_lines,
        )
        processing_mode = "prefiltered_chunked" if preprocessed.applied else "chunked"
        if preprocessed.applied:
            await _progress(
                "log_split",
                f"日志共 {total_lines} 行，规则清洗保留 {preprocessed.kept_lines} 行、"
                f"过滤 {preprocessed.removed_lines} 行，已拆分为 {len(segments)} 块",
            )
        else:
            await _progress(
                "log_split",
                f"日志共 {total_lines} 行，已自适应拆分为 {len(segments)} 块",
            )

    await _progress("log_extract", f"正在并发提取 {len(segments)} 个日志块")
    logger.info(
        "AI 日志提取开始 model=%s mode=%s segments=%d total_lines=%d concurrency=%d",
        machine_model or DEFAULT_ID,
        processing_mode,
        len(segments),
        total_lines,
        concurrency,
    )
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
            "retry_count": structured.get("retry_count", 0),
            "extraction_duration_ms": round((perf_counter() - started_at) * 1000),
        }
        logger.info(
            "AI 日志提取完成 model=%s mode=%s segments=%d success=%d failed=%d errors=%d duration_ms=%d",
            machine_model or DEFAULT_ID,
            processing_mode,
            len(segments),
            stats["successful_segments"],
            stats["failed_segments"],
            stats["error_count"],
            stats["extraction_duration_ms"],
        )
        return {"extracted": flattened, "stats": stats, "structured": structured}
    except Exception as e:  # noqa: BLE001
        logger.warning("AI 日志提取失败，回退编码级: %s", e)
        await _progress("log_merge", "AI 提取失败，正在执行编码级回退扫描")
        extracted, enc_stats = extract_log_context(raw_text, mode=mode)
        stats = {**stats_base, "ai_extracted": False, "segment_count": 0,
                 "error_count": enc_stats.get("matched_lines", 0),
                 "processing_mode": "regex_fallback",
                 "extraction_duration_ms": round((perf_counter() - started_at) * 1000),
                 "fallback_error": str(e), **enc_stats}
        return {"extracted": extracted, "stats": stats, "structured": None}


__all__ = [
    "process_log",
    "LogSegmenter",
    "AILogExtractor",
    "PromptRegistry",
    "ContextExtractor",
    "preprocess_log",
    "SMALL_LOG_MAX_LINES",
]

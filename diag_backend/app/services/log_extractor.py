"""
智能日志提取器 — 两级策略

1. 编码级提取（ContextExtractor）
   基于正则模式匹配，从日志中快速定位错误/异常行并提取上下文窗口。
   无 AI 开销，毫秒级返回，适用于所有日志格式的快速预过滤。

2. AI 级提取（由 LLMService 提供）
   当编码级提取结果仍超出 token 预算，或需要更深入的语义理解时，
   将编码结果发送给 LLM 做二次精炼：去噪、归类、生成结构化摘要。

3. 组合模式（recommended）
   编码提取 → 判断是否需 AI 精炼 → 最终送入诊断 LLM。
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 错误行匹配模式（按优先级/类别排列）
# ──────────────────────────────────────────────

# 日志级别标记
LOG_LEVEL_PATTERNS = [
    re.compile(r'\bFATAL\b', re.IGNORECASE),
    re.compile(r'\bCRITICAL\b', re.IGNORECASE),
    re.compile(r'\bERROR\b', re.IGNORECASE),
    re.compile(r'\bWARN(?:ING)?\b', re.IGNORECASE),
]

# 明确的失败/异常关键字
FAILURE_PATTERNS = [
    re.compile(r'\bFAIL(?:ED|URE)?\b', re.IGNORECASE),
    re.compile(r'\bException\b', re.IGNORECASE),
    re.compile(r'\bError\b', re.IGNORECASE),
    re.compile(r'\bTraceback\b', re.IGNORECASE),
    re.compile(r'\bnon-zero\b', re.IGNORECASE),
    re.compile(r'\babort(?:ed|ing)?\b', re.IGNORECASE),
    re.compile(r'\bpanic\b', re.IGNORECASE),
]

# 硬件/服务器特定错误
HARDWARE_PATTERNS = [
    re.compile(r'\bUncorrectable\b', re.IGNORECASE),
    re.compile(r'\bCorrectable\b', re.IGNORECASE),
    re.compile(r'\bMCA\b'),                                # Machine Check Architecture
    re.compile(r'\bCE[Cc]?\b'),                            # Correctable Error
    re.compile(r'\bUE[Cc]?\b'),                            # Uncorrectable Error
    re.compile(r'\bSERR\b'),                               # System Error
    re.compile(r'\bPCIe?\b.*(?:err|fail|fatal|surprise)', re.IGNORECASE),
    re.compile(r'\b(?:DIMM|MEM|memory)\s*(?:err|fail|fatal)', re.IGNORECASE),
    re.compile(r'\b(?:CPU|PROC(?:ESSOR)?)\s*(?:err|fail|fatal|thermal|overheat)', re.IGNORECASE),
    re.compile(r'\b(?:DISK|HDD|SSD|NVMe|SATA)\s*(?:err|fail|fatal|smart)', re.IGNORECASE),
    re.compile(r'\b(?:FAN|PSU|POWER|TEMP(?:ERATURE)?)\s*(?:err|fail|fatal|warn)', re.IGNORECASE),
    re.compile(r'\bREDUNDANCY\s+LOST\b', re.IGNORECASE),
    re.compile(r'\bVOLTAGE\s*(?:err|fail|fault)', re.IGNORECASE),
]

# 超时/资源/状态类
GENERAL_PATTERNS = [
    re.compile(r'\btimeout\b', re.IGNORECASE),
    re.compile(r'\btimed?\s*out\b', re.IGNORECASE),
    re.compile(r'\bOOM\b'),
    re.compile(r'\bkilled\b', re.IGNORECASE),
    re.compile(r'\bdenied\b', re.IGNORECASE),
    re.compile(r'\brefus(?:e|ed|ing)\b', re.IGNORECASE),
]

# 中文关键词
CHINESE_PATTERNS = [
    re.compile(r'故障'),
    re.compile(r'异常'),
    re.compile(r'失败'),
    re.compile(r'超时'),
    re.compile(r'错误'),
    re.compile(r'不通过|未通过|不合格'),
    re.compile(r'告警|预警'),
]

# 所有模式合并（去重）
ERROR_PATTERNS: list[re.Pattern] = []
_seen = set()
for pattern_list in (LOG_LEVEL_PATTERNS, FAILURE_PATTERNS, HARDWARE_PATTERNS,
                     GENERAL_PATTERNS, CHINESE_PATTERNS):
    for pat in pattern_list:
        key = pat.pattern
        if key not in _seen:
            _seen.add(key)
            ERROR_PATTERNS.append(pat)


# ──────────────────────────────────────────────
# 上下文提取选项
# ──────────────────────────────────────────────

EXTRACTION_MODES = {
    "light": {
        "context_before": 10,
        "context_after": 5,
        "max_context_chars": 4000,
    },
    "balanced": {
        "context_before": 20,
        "context_after": 10,
        "max_context_chars": 8000,
    },
    "thorough": {
        "context_before": 30,
        "context_after": 15,
        "max_context_chars": 15000,
    },
}


# ──────────────────────────────────────────────
# 编码级上下文提取器
# ──────────────────────────────────────────────

class ContextExtractorResult:
    """编码级提取结果"""

    def __init__(self, extracted: str, stats: dict):
        self.extracted = extracted          # 提取后的日志文本
        self.stats = stats                  # 统计信息
        self.needs_ai_refine = stats.get("total_lines", 0) > 500

    def to_dict(self) -> dict:
        return {
            "extracted": self.extracted,
            "stats": self.stats,
            "needs_ai_refine": self.needs_ai_refine,
        }


class ContextExtractor:
    """
    编码级日志上下文提取器。

    基于正则模式匹配，从日志中提取错误/异常/失败行及其上下文窗口。
    不依赖 LLM，适用于快速日志预过滤。

    Usage:
        extractor = ContextExtractor()
        result = extractor.extract(log_text)
        print(result.extracted)
        print(result.stats)   # {"matched_lines": 5, "paragraphs": 2, ...}
    """

    def __init__(self, patterns: Optional[list[re.Pattern]] = None):
        self.patterns = patterns or ERROR_PATTERNS

    def extract(
        self,
        log_text: str,
        mode: str = "balanced",
        context_before: Optional[int] = None,
        context_after: Optional[int] = None,
        max_context_chars: Optional[int] = None,
        custom_patterns: Optional[list[re.Pattern]] = None,
    ) -> ContextExtractorResult:
        """
        执行编码级上下文提取。

        Args:
            log_text: 原始日志文本
            mode: 预置模式 "light" | "balanced" | "thorough"
            context_before: 匹配行前取多少行（覆盖 mode 设置）
            context_after: 匹配行后取多少行（覆盖 mode 设置）
            max_context_chars: 输出最大字符数（覆盖 mode 设置）
            custom_patterns: 额外自定义匹配模式

        Returns:
            ContextExtractorResult，包含提取文本和统计信息
        """
        config = EXTRACTION_MODES.get(mode, EXTRACTION_MODES["balanced"])
        ctx_before = context_before if context_before is not None else config["context_before"]
        ctx_after = context_after if context_after is not None else config["context_after"]
        max_chars = max_context_chars if max_context_chars is not None else config["max_context_chars"]

        patterns = self.patterns
        if custom_patterns:
            patterns = patterns + custom_patterns

        # 延迟导入，避免 log_processing 包入口与编码级回退之间形成初始化循环。
        from .log_processing.preprocessor import (
            BENIGN_ANOMALY_PATTERN,
            is_strong_anomaly_line,
        )

        lines = log_text.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return ContextExtractorResult(
                extracted="",
                stats={"matched_lines": 0, "paragraphs": 0, "total_lines": 0,
                       "severity_distribution": {}, "error_markers": []},
            )

        # ── 行级模式匹配 ──
        matched_indices: set[int] = set()
        error_markers: list[dict] = []   # [{line_idx, pattern_type, matched_text}]

        for i, line in enumerate(lines):
            for pat in patterns:
                m = pat.search(line)
                if m:
                    if BENIGN_ANOMALY_PATTERN.search(line) and not is_strong_anomaly_line(line):
                        continue
                    matched_indices.add(i)
                    error_markers.append({
                        "line_idx": i,
                        "matched_text": m.group()[:60],
                        "line_snippet": line[:120].strip(),
                    })
                    break   # 每行只记一个匹配

        matched_count = len(matched_indices)

        # ── 统计严重级别分布 ──
        severity_dist: dict[str, int] = {}
        for idx in matched_indices:
            line = lines[idx]
            for level_pat in LOG_LEVEL_PATTERNS:
                if level_pat.search(line):
                    key = level_pat.pattern.strip(r"\b")
                    severity_dist[key] = severity_dist.get(key, 0) + 1
                    break

        # ── 无匹配时的降级策略 ──
        if matched_count == 0:
            tail = self._tail_lines(lines, n=50)
            tail_text = "".join(tail)
            return ContextExtractorResult(
                extracted=tail_text,
                stats={
                    "matched_lines": 0,
                    "paragraphs": 0,
                    "total_lines": total_lines,
                    "total_chars": len(log_text),
                    "extracted_chars": len(tail_text),
                    "severity_distribution": severity_dist,
                    "error_markers": error_markers,
                    "is_truncated": False,
                    "note": "未匹配到错误模式，已取最后 50 行作为上下文",
                },
            )

        # ── 构建上下文窗口（带段落合并） ──
        paragraphs: list[tuple[int, int, set[int]]] = self._build_paragraphs(
            matched_indices, lines, ctx_before, ctx_after
        )
        paragraph_count = len(paragraphs)

        # ── 生成输出文本 ──
        result_parts: list[str] = []
        for p_idx, (start, end, err_indices) in enumerate(paragraphs):
            section_lines: list[str] = []
            for i in range(start, end + 1):
                if i in err_indices:
                    # 错误行用 >>> 标注，同时保留原始行内容
                    section_lines.append(f">>> {lines[i]}")
                else:
                    section_lines.append(f"    {lines[i]}")
            result_parts.append("\n".join(section_lines))

        separator = "\n\n[... 段落间隔 ...]\n\n"
        extracted = separator.join(result_parts)

        # ── 字符数限制 ──
        is_truncated = False
        if len(extracted) > max_chars:
            extracted = extracted[:max_chars]
            # 尽量避免截断在行中间
            last_newline = extracted.rfind("\n")
            if last_newline > max_chars * 0.8:
                extracted = extracted[:last_newline]
            extracted += "\n\n[注意：日志上下文已截断至字符数上限]"
            is_truncated = True

        # ── 返回结果 ──
        stats = {
            "matched_lines": matched_count,
            "paragraphs": paragraph_count,
            "total_lines": total_lines,
            "total_chars": len(log_text),
            "extracted_chars": len(extracted),
            "severity_distribution": severity_dist,
            "error_markers": error_markers[:20],   # 只保留前 20 条
            "is_truncated": is_truncated,
            "note": None,
        }

        return ContextExtractorResult(extracted=extracted, stats=stats)

    def _build_paragraphs(
        self,
        matched_indices: set[int],
        lines: list[str],
        ctx_before: int,
        ctx_after: int,
    ) -> list[tuple[int, int, set[int]]]:
        """构建上下文段落（合并重叠窗口）。"""
        if not matched_indices:
            return []

        sorted_indices = sorted(matched_indices)
        # 为每个匹配行确定窗口范围
        windows: list[tuple[int, int, set[int]]] = []
        for idx in sorted_indices:
            start = max(0, idx - ctx_before)
            end = min(len(lines) - 1, idx + ctx_after)
            windows.append((start, end, {idx}))

        # 合并重叠/相邻窗口
        merged: list[tuple[int, int, set[int]]] = [windows[0]]
        for start, end, errs in windows[1:]:
            prev_start, prev_end, prev_errs = merged[-1]
            if start <= prev_end + 1:   # 相邻也合并
                merged[-1] = (prev_start, max(prev_end, end), prev_errs | errs)
            else:
                merged.append((start, end, errs))

        return merged

    def _tail_lines(self, lines: list[str], n: int = 50) -> list[str]:
        """降级：取最后 n 行，并在开头标记。"""
        tail = lines[-min(len(lines), n):]
        return [
            f"[上下文提取 — 未匹配到错误模式，已取最后 {len(tail)} 行]\n",
            *[f"    {line}\n" for line in tail],
        ]


# ──────────────────────────────────────────────
# 便捷函数
# ──────────────────────────────────────────────

def extract_log_context(
    log_text: str,
    mode: str = "balanced",
    context_before: Optional[int] = None,
    context_after: Optional[int] = None,
    max_context_chars: Optional[int] = None,
) -> tuple[str, dict]:
    """
    快捷函数：对一段日志执行编码级上下文提取。

    Args:
        log_text: 原始日志文本
        mode: "light" | "balanced" | "thorough"
        其余参数同 ContextExtractor.extract

    Returns:
        (extracted_text, stats_dict)
    """
    extractor = ContextExtractor()
    result = extractor.extract(
        log_text=log_text,
        mode=mode,
        context_before=context_before,
        context_after=context_after,
        max_context_chars=max_context_chars,
    )
    return result.extracted, result.stats


# ──────────────────────────────────────────────
# AI 级提取的 Prompt 模板
# ──────────────────────────────────────────────

LOG_EXTRACTION_SYSTEM_PROMPT = """你是一个日志解析专家。你的任务是分析一段设备测试日志，提取其中的关键错误信息。

请遵守以下原则：
1. 只提取与故障相关的行和上下文，忽略 INFO/DEBUG 等非关键信息
2. 保留错误行的上下文（前后各 2-3 行）
3. 对同类错误进行归并，不要重复列出完全相同的错误
4. 如果日志中包含堆栈信息，保留完整堆栈
5. 输出时保留原始日志的行号和内容，不要改写"""

LOG_EXTRACTION_USER_PROMPT_TPL = """以下是设备测试日志的第 {segment_index}/{segment_count} 个处理块，
对应原始日志第 {segment_start_line}-{segment_end_line} 行（本块共 {total_lines} 行，{total_chars} 字符）。

请分析以下日志，按模板输出 JSON 格式的结果。

```
{log_text}
```

请以以下 JSON 格式返回分析结果（所有字段必填）：
```json
{{
  "errors": [
    {{
      "severity": "FATAL|ERROR|WARN|INFO",
      "line_number": 123,
      "line_content": "原始日志行内容",
      "context_before": ["前一行", "...（最多3行）"],
      "context_after": ["后一行", "...（最多3行）"],
      "analysis": "该错误行的简要分析和可能含义"
    }}
  ],
  "summary": "对整个日志的错误情况做 50-100 字摘要，包括：共有几个关键错误、最严重的错误是什么、整体趋势",
  "has_critical_errors": true,
  "suggested_root_cause": "根据已有信息初步判断可能的根因"
}}
```

line_number 必须填写该错误在原始完整日志中的全局行号，而不是处理块内的相对行号。"""


__all__ = [
    "ContextExtractor",
    "ContextExtractorResult",
    "extract_log_context",
    "ERROR_PATTERNS",
    "EXTRACTION_MODES",
    "LOG_EXTRACTION_SYSTEM_PROMPT",
    "LOG_EXTRACTION_USER_PROMPT_TPL",
]

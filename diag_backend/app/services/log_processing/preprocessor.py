"""大日志规则预清洗：过滤普通低级别事件，同时保留异常上下文和原始行号。"""

from __future__ import annotations

import re
from dataclasses import dataclass


LOG_LEVEL_PATTERN = re.compile(
    r"^\s*(?:\x1b\[[0-9;]*m)?[\[(]?"
    r"(?P<level>TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)"
    r"[\])]?\s*(?::|-|\||\s)",
    re.IGNORECASE,
)
DELIMITED_LOG_LEVEL_PATTERN = re.compile(
    r"^.{0,140}?(?:\s-\s|\s\|\s)"
    r"(?P<level>TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)"
    r"(?=\s*(?:-|\||:|\]))",
    re.IGNORECASE,
)
BRACKETED_LOG_LEVEL_PATTERN = re.compile(
    r"^.{0,140}?\[\s*"
    r"(?P<level>TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)"
    r"\s*\]",
    re.IGNORECASE,
)
ANOMALY_HINT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:fail(?:ed|ure)?|error|warn(?:ing)?|timeout|exception|panic|"
    r"abort(?:ed)?|fault|offline|assert(?:ion)?|fatal|critical|ng)"
    r"(?![A-Za-z0-9_])|失败|错误|异常|超时|故障|离线|中止|崩溃",
    re.IGNORECASE,
)
STRONG_ANOMALY_PATTERN = re.compile(
    r"\[(?:FAIL|FAILED)\]"
    r"|\btraceback\b"
    r"|\b(?:panic|fatal|offline)\b"
    r"|\bexception\b"
    r"|\b(?:fail(?:ed|ure)?|error|fault|critical)\b[^\n]{0,100}\bexceeded\b"
    r"|\b(?:error|failure|fault|critical(?:_warning| warning)?)\s*(?:count|entries)?\s*[:=]\s*(?!0(?:x0+)?\b)\d+\b"
    r"|失败|崩溃|离线|严重错误",
    re.IGNORECASE,
)
BENIGN_ANOMALY_PATTERN = re.compile(
    r"\[(?:PASS|PASSED)\]"
    r"|\bno\s+(?:errors?|failures?|faults?|exceptions?)\b"
    r"|\bno\s+find\s+[^\n]*(?:error|timeout|abort|fault)\b"
    r"|\b(?:errors?|warnings?|failures?|faults?|timeouts?|critical(?:_warning| warning)?)\b"
    r"[^\n:=]{0,60}[:=]\s*(?:0|0x0+)\b"
    r"|\b(?:run\s+cmd|check\s+item)\b"
    r"|\b(?:cemsk|threshold)\b"
    r"|\berror\s+information\s*\([^\n]*\blog\b"
    r"|\|\s*ok\s*\|"
    r"|正常|成功|通过|未发现|无异常|无错误",
    re.IGNORECASE,
)
ALWAYS_KEEP_LEVELS = {"WARN", "ERROR", "FATAL", "CRITICAL"}
LOG_LEVEL_SCAN_CHARS = 160


@dataclass(frozen=True)
class PreprocessedLog:
    text: str
    source_line_numbers: tuple[int, ...]
    original_lines: int
    kept_lines: int
    removed_lines: int
    recognized_level_lines: int
    anomaly_entries: int
    applied: bool

    def stats(self) -> dict:
        retention_ratio = self.kept_lines / self.original_lines if self.original_lines else 1.0
        return {
            "preprocessing_applied": self.applied,
            "preprocessing_original_lines": self.original_lines,
            "preprocessing_kept_lines": self.kept_lines,
            "preprocessing_removed_lines": self.removed_lines,
            "preprocessing_retention_ratio": round(retention_ratio, 4),
            "preprocessing_level_lines": self.recognized_level_lines,
            "preprocessing_anomaly_entries": self.anomaly_entries,
        }


@dataclass(frozen=True)
class _LogEntry:
    start: int
    end: int
    level: str


def _normalize_level(raw_level: str) -> str:
    level = raw_level.upper()
    return "WARN" if level == "WARNING" else level


def _build_entries(lines: list[str]) -> tuple[list[_LogEntry], int]:
    structured_starts: list[tuple[int, str]] = []
    simple_starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        header = line[:LOG_LEVEL_SCAN_CHARS]
        match = DELIMITED_LOG_LEVEL_PATTERN.search(header)
        if match is None:
            match = BRACKETED_LOG_LEVEL_PATTERN.search(header)
        if match:
            structured_starts.append(
                (index, _normalize_level(match.group("level")))
            )
            continue

        match = LOG_LEVEL_PATTERN.search(header)
        if match:
            simple_starts.append((index, _normalize_level(match.group("level"))))

    # 一旦日志中存在稳定的结构化级别格式，就只使用该格式切分事件。
    # 这能避免命令输出里的 "Warning Threshold"、"Error Information"
    # 被误判为新的 WARNING/ERROR 日志头。
    level_starts = (
        structured_starts
        if len(structured_starts) >= 3
        else sorted(structured_starts + simple_starts)
    )

    if not level_starts:
        return [], 0

    entries: list[_LogEntry] = []
    first_start = level_starts[0][0]
    if first_start > 0:
        entries.append(_LogEntry(0, first_start, ""))
    for position, (start, level) in enumerate(level_starts):
        end = level_starts[position + 1][0] if position + 1 < len(level_starts) else len(lines)
        entries.append(_LogEntry(start, end, level))
    return entries, len(level_starts)


def is_strong_anomaly_line(line: str) -> bool:
    """判断一行是否包含足以覆盖普通噪声规则的强异常证据。"""
    if re.search(
        r"\[(?:FAIL|FAILED)\]|\b(?:traceback|panic|fatal|offline|exception)\b"
        r"|\b(?:fail(?:ed|ure)?|error|fault|critical)\b[^\n]{0,100}\bexceeded\b"
        r"|失败|崩溃|离线|严重错误",
        line,
        re.IGNORECASE,
    ):
        return True
    if STRONG_ANOMALY_PATTERN.search(line) is None:
        return False
    # 明确的成功/零计数描述仍然不能作为异常锚点。
    return not bool(
        re.search(
            r"\[(?:PASS|PASSED)\]|\bno\s+(?:errors?|failures?|faults?|exceptions?)\b"
            r"|[:=]\s*(?:0|0x0+)\b|正常|成功|通过|无异常|无错误",
            line,
            re.IGNORECASE,
        )
    )


def is_anomaly_line(line: str) -> bool:
    """按强证据优先、普通异常词次之的顺序判断异常行。"""
    if is_strong_anomaly_line(line):
        return True
    return (
        ANOMALY_HINT_PATTERN.search(line) is not None
        and BENIGN_ANOMALY_PATTERN.search(line) is None
    )


def preprocess_log(
    raw_text: str,
    *,
    context_before: int = 10,
    context_after: int = 20,
    min_level_markers: int = 3,
) -> PreprocessedLog:
    """保留异常事件及其上下文，过滤其余 INFO/DEBUG/TRACE 事件。"""
    lines = raw_text.splitlines(keepends=True)
    total_lines = len(lines)
    if not lines:
        return PreprocessedLog("", (), 0, 0, 0, 0, 0, False)

    entries, recognized = _build_entries(lines)
    if recognized < max(1, min_level_markers):
        # 未识别出稳定日志格式时，只围绕强异常证据提取，避免整份大日志
        # 因格式未知而直接绕过清洗；没有强锚点时保留原文以防误删。
        strong_indices = {
            index for index, line in enumerate(lines) if is_strong_anomaly_line(line)
        }
        if strong_indices:
            keep_indices: set[int] = set()
            before = max(0, context_before)
            after = max(0, context_after)
            for index in strong_indices:
                keep_indices.update(
                    range(max(0, index - before), min(total_lines, index + after + 1))
                )
            ordered_indices = sorted(keep_indices)
            cleaned_lines = [f"[L{index + 1}] {lines[index]}" for index in ordered_indices]
            kept_lines = len(ordered_indices)
            return PreprocessedLog(
                "".join(cleaned_lines),
                tuple(index + 1 for index in ordered_indices),
                total_lines,
                kept_lines,
                total_lines - kept_lines,
                recognized,
                len(strong_indices),
                kept_lines < total_lines,
            )
        return PreprocessedLog(
            raw_text,
            tuple(range(1, total_lines + 1)),
            total_lines,
            total_lines,
            0,
            recognized,
            0,
            False,
        )

    anomaly_indices: set[int] = set()
    before = max(0, context_before)
    after = max(0, context_after)
    for entry in entries:
        if entry.level in ALWAYS_KEEP_LEVELS:
            anomaly_indices.add(entry.start)
        anomaly_indices.update(
            index
            for index in range(entry.start, entry.end)
            if is_anomaly_line(lines[index])
        )

    keep_indices: set[int] = set()
    for index in anomaly_indices:
        keep_start = max(0, index - before)
        keep_end = min(total_lines, index + after + 1)
        keep_indices.update(range(keep_start, keep_end))

    ordered_indices = sorted(keep_indices)
    if len(ordered_indices) == total_lines:
        return PreprocessedLog(
            raw_text,
            tuple(range(1, total_lines + 1)),
            total_lines,
            total_lines,
            0,
            recognized,
            len(anomaly_indices),
            False,
        )
    cleaned_lines = [f"[L{index + 1}] {lines[index]}" for index in ordered_indices]
    kept_lines = len(ordered_indices)
    return PreprocessedLog(
        "".join(cleaned_lines),
        tuple(index + 1 for index in ordered_indices),
        total_lines,
        kept_lines,
        total_lines - kept_lines,
        recognized,
        len(anomaly_indices),
        True,
    )


__all__ = [
    "ANOMALY_HINT_PATTERN",
    "BENIGN_ANOMALY_PATTERN",
    "BRACKETED_LOG_LEVEL_PATTERN",
    "DELIMITED_LOG_LEVEL_PATTERN",
    "LOG_LEVEL_SCAN_CHARS",
    "LOG_LEVEL_PATTERN",
    "STRONG_ANOMALY_PATTERN",
    "PreprocessedLog",
    "is_anomaly_line",
    "is_strong_anomaly_line",
    "preprocess_log",
]

"""
日志分段器 — 按行将原始日志切成适合 AI 模型上下文窗口的段落。

设计原则：
- 在行边界切分，避免把一条日志行从中间切断。
- 段间保留少量重叠（overlap），降低跨段错误上下文丢失的概率。
- 单行长于 max_chars 时独占一段（不强行截断行内容）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LogSegment:
    """A log chunk with its position in the original file."""

    text: str
    start_line: int
    end_line: int
    index: int


class LogSegmenter:
    """将日志文本按字符预算切分为若干段落。"""

    @staticmethod
    def split(text: str, max_chars: int = 12000, overlap: int = 200) -> list[str]:
        """
        按行切分日志为段落。

        Args:
            text: 原始日志文本
            max_chars: 每段最大字符数（依据提取模型上下文窗口推算）
            overlap: 段间重叠字符数，保留上下文连续性

        Returns:
            段落字符串列表；空文本返回 []
        """
        return [segment.text for segment in LogSegmenter.split_with_metadata(text, max_chars, overlap)]

    @staticmethod
    def split_with_metadata(
        text: str,
        max_chars: int = 12000,
        overlap: int = 200,
    ) -> list[LogSegment]:
        """Split on line boundaries and retain global line ranges."""
        if not text:
            return []
        if max_chars <= 0:
            max_chars = 12000

        lines = text.splitlines(keepends=True)
        segments: list[LogSegment] = []
        start = 0

        while start < len(lines):
            end = start
            char_count = 0
            while end < len(lines):
                line_len = len(lines[end])
                if end > start and char_count + line_len > max_chars:
                    break
                char_count += line_len
                end += 1

            segments.append(
                LogSegment(
                    text="".join(lines[start:end]),
                    start_line=start + 1,
                    end_line=end,
                    index=len(segments),
                )
            )
            if end >= len(lines):
                break

            overlap_start = end
            overlap_chars = 0
            while overlap_start > start:
                candidate_len = len(lines[overlap_start - 1])
                if overlap_chars + candidate_len > overlap:
                    break
                overlap_start -= 1
                overlap_chars += candidate_len

            # Always advance by at least one source line.
            start = max(start + 1, overlap_start if overlap_chars else end)

        logger.debug(
            "日志分段完成：共 %d 段（max_chars=%d, overlap=%d）",
            len(segments),
            max_chars,
            overlap,
        )
        return segments

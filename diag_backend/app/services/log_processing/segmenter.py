"""
日志分段器 — 按行将原始日志切成适合 AI 模型上下文窗口的段落。

设计原则：
- 在行边界切分，避免把一条日志行从中间切断。
- 段间保留少量重叠（overlap），降低跨段错误上下文丢失的概率。
- 单行长于 max_chars 时按字符安全切分，并保留原始行号与行内偏移。
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
    source_line_numbers: tuple[int, ...] = ()
    source_char_offsets: tuple[int, ...] = ()


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
        source_line_numbers: list[int] | tuple[int, ...] | None = None,
    ) -> list[LogSegment]:
        """Split on line boundaries and retain global line ranges."""
        if not text:
            return []
        if max_chars <= 0:
            max_chars = 12000
        overlap = min(max(0, overlap), max_chars // 4)

        lines = text.splitlines(keepends=True)
        if source_line_numbers is not None and len(source_line_numbers) != len(lines):
            raise ValueError("source_line_numbers 数量必须与日志行数一致")
        pieces: list[tuple[str, int, int]] = []
        for index, line in enumerate(lines):
            source_line = source_line_numbers[index] if source_line_numbers is not None else index + 1
            if len(line) <= max_chars:
                pieces.append((line, source_line, 0))
                continue
            for offset in range(0, len(line), max_chars):
                pieces.append((line[offset : offset + max_chars], source_line, offset))

        segments: list[LogSegment] = []
        start = 0

        while start < len(pieces):
            end = start
            char_count = 0
            while end < len(pieces):
                line_len = len(pieces[end][0])
                if end > start and char_count + line_len > max_chars:
                    break
                char_count += line_len
                end += 1

            piece_slice = pieces[start:end]
            preserve_mapping = source_line_numbers is not None or any(
                offset > 0 or len(piece) == max_chars
                for piece, _line, offset in piece_slice
            )
            source_lines = tuple(piece[1] for piece in piece_slice) if preserve_mapping else ()
            source_offsets = tuple(piece[2] for piece in piece_slice) if preserve_mapping else ()
            segments.append(
                LogSegment(
                    text="".join(piece[0] for piece in piece_slice),
                    start_line=piece_slice[0][1],
                    end_line=piece_slice[-1][1],
                    index=len(segments),
                    source_line_numbers=source_lines,
                    source_char_offsets=source_offsets,
                )
            )
            if end >= len(pieces):
                break

            overlap_start = end
            overlap_chars = 0
            while overlap_start > start:
                candidate_len = len(pieces[overlap_start - 1][0])
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

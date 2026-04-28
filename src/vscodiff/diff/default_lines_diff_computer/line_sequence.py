from __future__ import annotations

from vscodiff.common.char_code import CharCode
from vscodiff.common.offset_range import OffsetRange
from vscodiff.diff.default_lines_diff_computer.algorithms.diff_algorithm import (
    Sequence,
)


class LineSequence(Sequence):
    def __init__(self, trimmed_hash: list[int], lines: list[str]):
        self._trimmed_hash = trimmed_hash
        self._lines = lines

    def get_element(self, offset: int) -> int:
        return self._trimmed_hash[offset]

    @property
    def length(self) -> int:
        return len(self._trimmed_hash)

    def get_boundary_score(self, length: int) -> int:
        indentation_before = (
            0 if length == 0 else _get_indentation(self._lines[length - 1])
        )
        indentation_after = (
            0 if length == len(self._lines) else _get_indentation(self._lines[length])
        )
        return 1000 - (indentation_before + indentation_after)

    def get_text(self, range_: OffsetRange) -> str:
        return "\n".join(self._lines[range_.start : range_.end_exclusive])

    def is_strongly_equal(self, offset1: int, offset2: int) -> bool:
        return self._lines[offset1] == self._lines[offset2]


def _get_indentation(s: str) -> int:
    i = 0
    while i < len(s) and (ord(s[i]) == CharCode.SPACE or ord(s[i]) == CharCode.TAB):
        i += 1

    return i

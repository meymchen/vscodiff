from __future__ import annotations

from enum import IntEnum
from typing import Literal

from vscodiff.common.char_code import CharCode
from vscodiff.common.lists_find import (
    find_first_monotonous,
    find_last_idx_monotonous,
    find_last_monotonous,
)
from vscodiff.common.offset_range import OffsetRange
from vscodiff.common.position import Position
from vscodiff.common.range import Range
from vscodiff.diff.default_lines_diff_computer.algorithms.diff_algorithm import (
    Sequence,
)
from vscodiff.diff.default_lines_diff_computer.utils import is_space


class LinesSliceCharSequence(Sequence):
    def __init__(
        self,
        lines: list[str],
        range_: Range,
        consider_whitespace_changes: bool,
    ):
        self.lines = lines
        self._range = range_
        self.consider_whitespace_changes = consider_whitespace_changes

        self._elements: list[int] = []
        self._first_element_offset_by_line_idx: list[int] = []
        self._line_start_offsets: list[int] = []
        self._trimmed_ws_lengths_by_line_idx: list[int] = []

        self._first_element_offset_by_line_idx.append(0)
        for line_number in range(range_.start_line, range_.end_line + 1):
            line = lines[line_number - 1]
            line_start_offset = 0
            if line_number == range_.start_line and range_.start_column > 1:
                line_start_offset = range_.start_column - 1
                line = line[line_start_offset:]

            self._line_start_offsets.append(line_start_offset)

            trimmed_ws_length = 0
            if not consider_whitespace_changes:
                trimmed_start_line = line.lstrip()
                trimmed_ws_length = len(line) - len(trimmed_start_line)
                line = trimmed_start_line.rstrip()

            self._trimmed_ws_lengths_by_line_idx.append(trimmed_ws_length)

            line_length = (
                min(
                    range_.end_column - 1 - line_start_offset - trimmed_ws_length,
                    len(line),
                )
                if line_number == range_.end_line
                else len(line)
            )
            for i in range(line_length):
                self._elements.append(ord(line[i]))

            if line_number < range_.end_line:
                self._elements.append(ord("\n"))
                self._first_element_offset_by_line_idx.append(len(self._elements))

    def __str__(self) -> str:
        return f'Slice: "{self.text}"'

    @property
    def text(self) -> str:
        return self.get_text(OffsetRange(0, self.length))

    def get_text(self, range_: OffsetRange) -> str:
        return "".join(
            chr(e) for e in self._elements[range_.start : range_.end_exclusive]
        )

    def get_element(self, offset: int) -> int:
        return self._elements[offset]

    @property
    def length(self) -> int:
        return len(self._elements)

    def get_boundary_score(self, length: int) -> int:
        prev_category = _get_category(self._elements[length - 1] if length > 0 else -1)
        next_category = _get_category(
            self._elements[length] if length < len(self._elements) else -1
        )

        if (
            prev_category == CharBoundaryCategory.LINE_BREAK_CR
            and next_category == CharBoundaryCategory.LINE_BREAK_LF
        ):
            return 0

        if prev_category == CharBoundaryCategory.LINE_BREAK_LF:
            return 150

        score = 0
        if prev_category != next_category:
            score += 10
            if (
                prev_category == CharBoundaryCategory.WORD_LOWER
                and next_category == CharBoundaryCategory.WORD_UPPER
            ):
                score += 1

        score += _get_category_boundary_score(prev_category)
        score += _get_category_boundary_score(next_category)

        return score

    def translate_offset(
        self,
        offset: int,
        preference: Literal["left", "right"] = "right",
    ) -> Position:
        i = find_last_idx_monotonous(
            self._first_element_offset_by_line_idx, lambda value: value <= offset
        )
        line_offset = offset - self._first_element_offset_by_line_idx[i]
        return Position(
            self._range.start_line + i,
            1
            + self._line_start_offsets[i]
            + line_offset
            + (
                0
                if line_offset == 0 and preference == "left"
                else self._trimmed_ws_lengths_by_line_idx[i]
            ),
        )

    def translate_range(self, range_: OffsetRange) -> Range:
        pos1 = self.translate_offset(range_.start, "right")
        pos2 = self.translate_offset(range_.end_exclusive, "left")
        if pos2.is_before(pos1):
            return Range.from_positions(pos2, pos2)

        return Range.from_positions(pos1, pos2)

    def find_word_containing(self, offset: int) -> OffsetRange | None:
        if offset < 0 or offset >= len(self._elements):
            return None

        if not _is_word_char(self._elements[offset]):
            return None

        start = offset
        while start > 0 and _is_word_char(self._elements[start - 1]):
            start -= 1

        end = offset
        while end < len(self._elements) and _is_word_char(self._elements[end]):
            end += 1

        return OffsetRange(start, end)

    def find_sub_word_containing(self, offset: int) -> OffsetRange | None:
        if offset < 0 or offset >= len(self._elements):
            return None

        if not _is_word_char(self._elements[offset]):
            return None

        start = offset
        while (
            start > 0
            and _is_word_char(self._elements[start - 1])
            and not _is_upper_case(self._elements[start])
        ):
            start -= 1

        end = offset
        while (
            end < len(self._elements)
            and _is_word_char(self._elements[end])
            and not _is_upper_case(self._elements[end])
        ):
            end += 1

        return OffsetRange(start, end)

    def count_lines_in(self, range_: OffsetRange) -> int:
        return (
            self.translate_offset(range_.end_exclusive).line
            - self.translate_offset(range_.start).line
        )

    def is_strongly_equal(self, offset1: int, offset2: int) -> bool:
        return self._elements[offset1] == self._elements[offset2]

    def extend_to_full_lines(self, range_: OffsetRange) -> OffsetRange:
        start = (
            find_last_monotonous(
                self._first_element_offset_by_line_idx,
                lambda x: x <= range_.start,
            )
            or 0
        )
        end = find_first_monotonous(
            self._first_element_offset_by_line_idx,
            lambda x: range_.end_exclusive <= x,
        )
        if end is None:
            end = len(self._elements)

        return OffsetRange(start, end)


def _is_word_char(char_code: int) -> bool:
    return (
        (char_code >= CharCode.a and char_code <= CharCode.z)
        or (char_code >= CharCode.A and char_code <= CharCode.Z)
        or (char_code >= CharCode.DIGIT_0 and char_code <= CharCode.DIGIT_9)
    )


def _is_upper_case(char_code: int) -> bool:
    return char_code >= CharCode.A and char_code <= CharCode.Z


class CharBoundaryCategory(IntEnum):
    WORD_LOWER = 0
    WORD_UPPER = 1
    WORD_NUMBER = 2
    END = 3
    OTHER = 4
    SEPARATOR = 5
    SPACE = 6
    LINE_BREAK_CR = 7
    LINE_BREAK_LF = 8


_score: dict[CharBoundaryCategory, int] = {
    CharBoundaryCategory.WORD_LOWER: 0,
    CharBoundaryCategory.WORD_UPPER: 0,
    CharBoundaryCategory.WORD_NUMBER: 0,
    CharBoundaryCategory.END: 10,
    CharBoundaryCategory.OTHER: 2,
    CharBoundaryCategory.SEPARATOR: 30,
    CharBoundaryCategory.SPACE: 3,
    CharBoundaryCategory.LINE_BREAK_CR: 10,
    CharBoundaryCategory.LINE_BREAK_LF: 10,
}


def _get_category_boundary_score(category: CharBoundaryCategory) -> int:
    return _score[category]


def _get_category(char_code: int) -> CharBoundaryCategory:
    if char_code == CharCode.LINE_FEED:
        return CharBoundaryCategory.LINE_BREAK_LF

    if char_code == CharCode.CARRIAGE_RETURN:
        return CharBoundaryCategory.LINE_BREAK_CR

    if is_space(char_code):
        return CharBoundaryCategory.SPACE

    if char_code >= CharCode.a and char_code <= CharCode.z:
        return CharBoundaryCategory.WORD_LOWER

    if char_code >= CharCode.A and char_code <= CharCode.Z:
        return CharBoundaryCategory.WORD_UPPER

    if char_code >= CharCode.DIGIT_0 and char_code <= CharCode.DIGIT_9:
        return CharBoundaryCategory.WORD_NUMBER

    if char_code == -1:
        return CharBoundaryCategory.END

    if char_code == CharCode.COMMA or char_code == CharCode.SEMICOLON:
        return CharBoundaryCategory.SEPARATOR

    return CharBoundaryCategory.OTHER

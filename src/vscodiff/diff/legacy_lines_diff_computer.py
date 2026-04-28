from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from vscodiff.common.asserts import check_adjacent_items
from vscodiff.common.char_code import CharCode
from vscodiff.common.diff.diff import LcsDiff, Sequence
from vscodiff.common.diff.diff_change import DiffChange, DiffResult
from vscodiff.common.line_range import LineRange
from vscodiff.common.range import Range
from vscodiff.common.strings import (
    first_non_whitespace_index,
    last_non_whitespace_index,
)
from vscodiff.diff.lines_diff_computer import (
    LinesDiff,
    LinesDiffComputer,
    LinesDiffComputerOptions,
)
from vscodiff.diff.range_mapping import DetailedLineRangeMapping, RangeMapping

MINIMUM_MATCHING_CHARACTER_LENGTH = 3


class LegacyLinesDiffComputer(LinesDiffComputer):
    def compute_diff(
        self,
        original_lines: list[str],
        modified_lines: list[str],
        options: LinesDiffComputerOptions,
    ) -> LinesDiff:
        diff_computer = DiffComputer(
            original_lines,
            modified_lines,
            DiffComputerOpts(
                max_computation_time=options.max_computation_time_ms,
                should_ignore_trim_whitespace=options.ignore_trim_whitespace,
                should_compute_char_changes=True,
                should_make_pretty_diff=True,
                should_post_process_char_changes=True,
            ),
        )
        result = diff_computer.compute_diff()
        changes: list[DetailedLineRangeMapping] = []
        last_change: DetailedLineRangeMapping | None = None

        for c in result.changes:
            if c.original_end_line_number == 0:
                original_range = LineRange(
                    c.original_start_line_number + 1,
                    c.original_start_line_number + 1,
                )
            else:
                original_range = LineRange(
                    c.original_start_line_number,
                    c.original_end_line_number + 1,
                )

            if c.modified_end_line_number == 0:
                modified_range = LineRange(
                    c.modified_start_line_number + 1,
                    c.modified_start_line_number + 1,
                )
            else:
                modified_range = LineRange(
                    c.modified_start_line_number,
                    c.modified_end_line_number + 1,
                )

            change = DetailedLineRangeMapping(
                original_range,
                modified_range,
                [
                    RangeMapping(
                        Range(
                            cc.original_start_line_number,
                            cc.original_start_column,
                            cc.original_end_line_number,
                            cc.original_end_column,
                        ),
                        Range(
                            cc.modified_start_line_number,
                            cc.modified_start_column,
                            cc.modified_end_line_number,
                            cc.modified_end_column,
                        ),
                    )
                    for cc in c.char_changes
                ]
                if c.char_changes is not None
                else None,
            )
            if last_change is not None:
                if (
                    last_change.modified.end_line_exclusive
                    == change.modified.start_line
                    or last_change.original.end_line_exclusive
                    == change.original.start_line
                ):
                    change = DetailedLineRangeMapping(
                        last_change.original.join(change.original),
                        last_change.modified.join(change.modified),
                        last_change.inner_changes + change.inner_changes
                        if last_change.inner_changes is not None
                        and change.inner_changes is not None
                        else None,
                    )
                    changes.pop()

            changes.append(change)
            last_change = change

        assert check_adjacent_items(
            changes,
            lambda m1, m2: (
                m2.original.start_line - m1.original.end_line_exclusive
                == m2.modified.start_line - m1.modified.end_line_exclusive
                and m1.original.end_line_exclusive < m2.original.start_line
                and m1.modified.end_line_exclusive < m2.modified.start_line
            ),
        )

        return LinesDiff(changes, [], result.quit_early)


@dataclass
class Change:
    original_start_line_number: int
    original_end_line_number: int
    modified_start_line_number: int
    modified_end_line_number: int


@dataclass
class CharChange:
    original_start_line_number: int
    original_start_column: int
    original_end_line_number: int
    original_end_column: int
    modified_start_line_number: int
    modified_start_column: int
    modified_end_line_number: int
    modified_end_column: int

    @staticmethod
    def create_from_diff_change(
        diff_change: DiffChange,
        original_char_sequence: CharSequence,
        modified_char_sequence: CharSequence,
    ) -> CharChange:
        original_start_line_number = original_char_sequence.get_start_line_number(
            diff_change.original_start
        )
        original_start_column = original_char_sequence.get_start_column(
            diff_change.original_start
        )
        original_end_line_number = original_char_sequence.get_end_line_number(
            diff_change.original_start + diff_change.original_length - 1
        )
        original_end_column = original_char_sequence.get_end_column(
            diff_change.original_start + diff_change.original_length - 1
        )

        modified_start_line_number = modified_char_sequence.get_start_line_number(
            diff_change.modified_start
        )
        modified_start_column = modified_char_sequence.get_start_column(
            diff_change.modified_start
        )
        modified_end_line_number = modified_char_sequence.get_end_line_number(
            diff_change.modified_start + diff_change.modified_length - 1
        )
        modified_end_column = modified_char_sequence.get_end_column(
            diff_change.modified_start + diff_change.modified_length - 1
        )

        return CharChange(
            original_start_line_number,
            original_start_column,
            original_end_line_number,
            original_end_column,
            modified_start_line_number,
            modified_start_column,
            modified_end_line_number,
            modified_end_column,
        )


@dataclass
class LineChange:
    original_start_line_number: int
    original_end_line_number: int
    modified_start_line_number: int
    modified_end_line_number: int
    char_changes: list[CharChange] | None

    @staticmethod
    def create_from_diff_result(
        should_ignore_trim_whitespace: bool,
        diff_change: DiffChange,
        original_line_sequence: LineSequence,
        modified_line_sequence: LineSequence,
        continue_char_diff: Callable[..., bool],
        should_compute_char_changes: bool,
        should_post_process_char_changes: bool,
    ) -> LineChange:
        char_changes: list[CharChange] | None = None

        if diff_change.original_length == 0:
            original_start_line_number = (
                original_line_sequence.get_start_line_number(diff_change.original_start)
                - 1
            )
            original_end_line_number = 0
        else:
            original_start_line_number = original_line_sequence.get_start_line_number(
                diff_change.original_start
            )
            original_end_line_number = original_line_sequence.get_end_line_number(
                diff_change.original_start + diff_change.original_length - 1
            )

        if diff_change.modified_length == 0:
            modified_start_line_number = (
                modified_line_sequence.get_start_line_number(diff_change.modified_start)
                - 1
            )
            modified_end_line_number = 0
        else:
            modified_start_line_number = modified_line_sequence.get_start_line_number(
                diff_change.modified_start
            )
            modified_end_line_number = modified_line_sequence.get_end_line_number(
                diff_change.modified_start + diff_change.modified_length - 1
            )

        if (
            should_compute_char_changes
            and diff_change.original_length > 0
            and diff_change.original_length < 20
            and diff_change.modified_length > 0
            and diff_change.modified_length < 20
            and continue_char_diff()
        ):
            original_char_sequence = original_line_sequence.create_char_sequence(
                should_ignore_trim_whitespace,
                diff_change.original_start,
                diff_change.original_start + diff_change.original_length - 1,
            )
            modified_char_sequence = modified_line_sequence.create_char_sequence(
                should_ignore_trim_whitespace,
                diff_change.modified_start,
                diff_change.modified_start + diff_change.modified_length - 1,
            )

            if (
                len(original_char_sequence.get_elements()) > 0
                and len(modified_char_sequence.get_elements()) > 0
            ):
                raw_changes = _compute_diff(
                    original_char_sequence,
                    modified_char_sequence,
                    continue_char_diff,
                    True,
                ).changes

                if should_post_process_char_changes:
                    raw_changes = _post_process_char_changes(raw_changes)

                char_changes = [
                    CharChange.create_from_diff_change(
                        rc, original_char_sequence, modified_char_sequence
                    )
                    for rc in raw_changes
                ]

        return LineChange(
            original_start_line_number,
            original_end_line_number,
            modified_start_line_number,
            modified_end_line_number,
            char_changes,
        )


class LineSequence(Sequence):
    def __init__(self, lines: list[str]):
        super().__init__()

        start_columns: list[int] = []
        end_columns: list[int] = []
        for i, line in enumerate(lines):
            start_columns.append(_get_first_non_blank_column(line, 1))
            end_columns.append(_get_last_non_blank_column(line, 1))

        self.lines = lines
        self._start_columns = start_columns
        self._end_columns = end_columns

    def get_elements(self) -> list[str]:
        elements: list[str] = []
        for i, line in enumerate(self.lines):
            elements.append(line[self._start_columns[i] - 1 : self._end_columns[i] - 1])

        return elements

    def get_strict_element(self, index: int) -> str:
        return self.lines[index]

    def get_start_line_number(self, i: int) -> int:
        return i + 1

    def get_end_line_number(self, i: int) -> int:
        return i + 1

    def create_char_sequence(
        self,
        should_ignore_trim_whitespace: bool,
        start_index: int,
        end_index: int,
    ) -> CharSequence:
        char_codes: list[int] = []
        line_numbers: list[int] = []
        columns: list[int] = []
        for index in range(start_index, end_index + 1):
            line_content = self.lines[index]
            start_column = (
                self._start_columns[index] if should_ignore_trim_whitespace else 1
            )
            end_column = (
                self._end_columns[index]
                if should_ignore_trim_whitespace
                else len(line_content) + 1
            )
            for col in range(start_column, end_column):
                char_codes.append(ord(line_content[col - 1]))
                line_numbers.append(index + 1)
                columns.append(col)

            if not should_ignore_trim_whitespace and index < end_index:
                char_codes.append(CharCode.LINE_FEED)
                line_numbers.append(index + 1)
                columns.append(len(line_content) + 1)

        return CharSequence(char_codes, line_numbers, columns)


class CharSequence(Sequence):
    def __init__(
        self,
        char_codes: list[int],
        line_numbers: list[int],
        columns: list[int],
    ):
        super().__init__()

        self._char_codes = char_codes
        self._line_numbers = line_numbers
        self._columns = columns

    def __str__(self) -> str:
        parts: list[str] = []
        for idx, s in enumerate(self._char_codes):
            ch = "\\n" if s == CharCode.LINE_FEED else chr(s)
            parts.append(f"{ch}-({self._line_numbers[idx]},{self._columns[idx]})")

        return "[" + ", ".join(parts) + "]"

    def _assert_index(self, index: int, arr: list[int]) -> None:
        if index < 0 or index >= len(arr):
            raise IndexError("Illegal index")

    def get_elements(self) -> list[int]:
        return self._char_codes

    def get_strict_element(self, index: int) -> str:
        return chr(self._char_codes[index])

    def get_start_line_number(self, i: int) -> int:
        if i > 0 and i == len(self._line_numbers):
            return self.get_end_line_number(i - 1)

        self._assert_index(i, self._line_numbers)
        return self._line_numbers[i]

    def get_end_line_number(self, i: int) -> int:
        if i == -1:
            return self.get_start_line_number(i + 1)

        self._assert_index(i, self._line_numbers)
        if self._char_codes[i] == CharCode.LINE_FEED:
            return self._line_numbers[i] + 1

        return self._line_numbers[i]

    def get_start_column(self, i: int) -> int:
        if i > 0 and i == len(self._columns):
            return self.get_end_column(i - 1)

        self._assert_index(i, self._columns)
        return self._columns[i]

    def get_end_column(self, i: int) -> int:
        if i == -1:
            return self.get_start_column(i + 1)

        self._assert_index(i, self._columns)
        if self._char_codes[i] == CharCode.LINE_FEED:
            return 1

        return self._columns[i] + 1


@dataclass
class DiffComputerOpts:
    should_compute_char_changes: bool
    should_post_process_char_changes: bool
    should_ignore_trim_whitespace: bool
    should_make_pretty_diff: bool
    max_computation_time: int


@dataclass
class DiffComputerResult:
    quit_early: bool
    changes: list[LineChange]


@dataclass
class DiffComputationResult:
    quit_early: bool
    identical: bool
    changes: list[LineChange]
    changes2: list[DetailedLineRangeMapping]


class DiffComputer:
    def __init__(
        self,
        original_lines: list[str],
        modified_lines: list[str],
        opts: DiffComputerOpts,
    ):
        self._should_compute_char_changes = opts.should_compute_char_changes
        self._should_post_process_char_changes = opts.should_post_process_char_changes
        self._should_ignore_trim_whitespace = opts.should_ignore_trim_whitespace
        self._should_make_pretty_diff = opts.should_make_pretty_diff
        self._original_lines = original_lines
        self._modified_lines = modified_lines
        self._original = LineSequence(original_lines)
        self._modified = LineSequence(modified_lines)

        self._continue_line_diff = _create_continue_processing_predicate(
            opts.max_computation_time
        )
        self._continue_char_diff = _create_continue_processing_predicate(
            0
            if opts.max_computation_time == 0
            else min(opts.max_computation_time, 5000)
        )

    def compute_diff(self) -> DiffComputerResult:
        if len(self._original.lines) == 1 and len(self._original.lines[0]) == 0:
            if len(self._modified.lines) == 1 and len(self._modified.lines[0]) == 0:
                return DiffComputerResult(quit_early=False, changes=[])

            return DiffComputerResult(
                quit_early=False,
                changes=[
                    LineChange(
                        original_start_line_number=1,
                        original_end_line_number=1,
                        modified_start_line_number=1,
                        modified_end_line_number=len(self._modified.lines),
                        char_changes=None,
                    )
                ],
            )

        if len(self._modified.lines) == 1 and len(self._modified.lines[0]) == 0:
            return DiffComputerResult(
                quit_early=False,
                changes=[
                    LineChange(
                        original_start_line_number=1,
                        original_end_line_number=len(self._original.lines),
                        modified_start_line_number=1,
                        modified_end_line_number=1,
                        char_changes=None,
                    )
                ],
            )

        diff_result = _compute_diff(
            self._original,
            self._modified,
            self._continue_line_diff,
            self._should_make_pretty_diff,
        )
        raw_changes = diff_result.changes
        quit_early = diff_result.quit_early

        if self._should_ignore_trim_whitespace:
            line_changes: list[LineChange] = []
            for change in raw_changes:
                line_changes.append(
                    LineChange.create_from_diff_result(
                        self._should_ignore_trim_whitespace,
                        change,
                        self._original,
                        self._modified,
                        self._continue_char_diff,
                        self._should_compute_char_changes,
                        self._should_post_process_char_changes,
                    )
                )

            return DiffComputerResult(quit_early=quit_early, changes=line_changes)

        result: list[LineChange] = []

        original_line_index = 0
        modified_line_index = 0
        i = -1
        length = len(raw_changes)
        while i < length:
            next_change = raw_changes[i + 1] if i + 1 < length else None
            original_stop = (
                next_change.original_start
                if next_change is not None
                else len(self._original_lines)
            )
            modified_stop = (
                next_change.modified_start
                if next_change is not None
                else len(self._modified_lines)
            )

            while (
                original_line_index < original_stop
                and modified_line_index < modified_stop
            ):
                original_line = self._original_lines[original_line_index]
                modified_line = self._modified_lines[modified_line_index]

                if original_line != modified_line:
                    original_start_column = _get_first_non_blank_column(
                        original_line, 1
                    )
                    modified_start_column = _get_first_non_blank_column(
                        modified_line, 1
                    )
                    while original_start_column > 1 and modified_start_column > 1:
                        original_char = ord(original_line[original_start_column - 2])
                        modified_char = ord(modified_line[modified_start_column - 2])
                        if original_char != modified_char:
                            break

                        original_start_column -= 1
                        modified_start_column -= 1

                    if original_start_column > 1 or modified_start_column > 1:
                        self._push_trim_whitespace_char_change(
                            result,
                            original_line_index + 1,
                            1,
                            original_start_column,
                            modified_line_index + 1,
                            1,
                            modified_start_column,
                        )

                    original_end_column = _get_last_non_blank_column(original_line, 1)
                    modified_end_column = _get_last_non_blank_column(modified_line, 1)
                    original_max_column = len(original_line) + 1
                    modified_max_column = len(modified_line) + 1
                    while (
                        original_end_column < original_max_column
                        and modified_end_column < modified_max_column
                    ):
                        original_char = ord(original_line[original_end_column - 1])
                        modified_char = ord(original_line[modified_end_column - 1])
                        if original_char != modified_char:
                            break

                        original_end_column += 1
                        modified_end_column += 1

                    if (
                        original_end_column < original_max_column
                        or modified_end_column < modified_max_column
                    ):
                        self._push_trim_whitespace_char_change(
                            result,
                            original_line_index + 1,
                            original_end_column,
                            original_max_column,
                            modified_line_index + 1,
                            modified_end_column,
                            modified_max_column,
                        )

                original_line_index += 1
                modified_line_index += 1

            if next_change is not None:
                result.append(
                    LineChange.create_from_diff_result(
                        self._should_ignore_trim_whitespace,
                        next_change,
                        self._original,
                        self._modified,
                        self._continue_char_diff,
                        self._should_compute_char_changes,
                        self._should_post_process_char_changes,
                    )
                )

                original_line_index += next_change.original_length
                modified_line_index += next_change.modified_length

            i += 1

        return DiffComputerResult(quit_early=quit_early, changes=result)

    def _push_trim_whitespace_char_change(
        self,
        result: list[LineChange],
        original_line_number: int,
        original_start_column: int,
        original_end_column: int,
        modified_line_number: int,
        modified_start_column: int,
        modified_end_column: int,
    ) -> None:
        if self._merge_trim_whitespace_char_change(
            result,
            original_line_number,
            original_start_column,
            original_end_column,
            modified_line_number,
            modified_start_column,
            modified_end_column,
        ):
            return

        char_changes: list[CharChange] | None = None
        if self._should_compute_char_changes:
            char_changes = [
                CharChange(
                    original_line_number,
                    original_start_column,
                    original_line_number,
                    original_end_column,
                    modified_line_number,
                    modified_start_column,
                    modified_line_number,
                    modified_end_column,
                )
            ]

        result.append(
            LineChange(
                original_line_number,
                original_line_number,
                modified_line_number,
                modified_line_number,
                char_changes,
            )
        )

    def _merge_trim_whitespace_char_change(
        self,
        result: list[LineChange],
        original_line_number: int,
        original_start_column: int,
        original_end_column: int,
        modified_line_number: int,
        modified_start_column: int,
        modified_end_column: int,
    ) -> bool:
        length = len(result)
        if length == 0:
            return False

        prev_change = result[length - 1]

        if (
            prev_change.original_end_line_number == 0
            or prev_change.modified_end_line_number == 0
        ):
            return False

        if (
            prev_change.original_end_line_number == original_line_number
            and prev_change.modified_end_line_number == modified_line_number
        ):
            if self._should_compute_char_changes and prev_change.char_changes:
                prev_change.char_changes.append(
                    CharChange(
                        original_line_number,
                        original_start_column,
                        original_line_number,
                        original_end_column,
                        modified_line_number,
                        modified_start_column,
                        modified_line_number,
                        modified_end_column,
                    )
                )
            return True

        if (
            prev_change.original_end_line_number + 1 == original_line_number
            and prev_change.modified_end_line_number + 1 == modified_line_number
        ):
            prev_change.original_end_line_number = original_line_number
            prev_change.modified_end_line_number = modified_line_number
            if self._should_compute_char_changes and prev_change.char_changes:
                prev_change.char_changes.append(
                    CharChange(
                        original_line_number,
                        original_start_column,
                        original_line_number,
                        original_end_column,
                        modified_line_number,
                        modified_start_column,
                        modified_line_number,
                        modified_end_column,
                    )
                )
            return True

        return False


def _compute_diff(
    original_sequence: Sequence,
    modified_sequence: Sequence,
    continue_processing_predicate: Callable[[int, int], bool],
    pretty: bool,
) -> DiffResult:
    diff_algo = LcsDiff(
        original_sequence, modified_sequence, continue_processing_predicate
    )
    return diff_algo.compute_diff(pretty)


def _post_process_char_changes(raw_changes: list[DiffChange]) -> list[DiffChange]:
    if len(raw_changes) <= 1:
        return raw_changes

    result = [raw_changes[0]]
    prev_change = result[0]

    for i in range(1, len(raw_changes)):
        curr_change = raw_changes[i]

        original_matching_length = curr_change.original_start - (
            prev_change.original_start + prev_change.original_length
        )
        modified_matching_length = curr_change.modified_start - (
            prev_change.modified_start + prev_change.modified_length
        )
        matching_length = min(original_matching_length, modified_matching_length)

        if matching_length < MINIMUM_MATCHING_CHARACTER_LENGTH:
            prev_change.original_length = (
                curr_change.original_start
                + curr_change.original_length
                - prev_change.original_start
            )
            prev_change.modified_length = (
                curr_change.modified_start
                + curr_change.modified_length
                - prev_change.modified_start
            )
        else:
            result.append(curr_change)
            prev_change = curr_change

    return result


def _get_first_non_blank_column(txt: str, default_value: int) -> int:
    r = first_non_whitespace_index(txt)
    if r == -1:
        return default_value

    return r + 1


def _get_last_non_blank_column(txt: str, default_value: int) -> int:
    r = last_non_whitespace_index(txt)
    if r == -1:
        return default_value

    return r + 2


def _create_continue_processing_predicate(
    maximum_runtime: int,
) -> Callable[..., bool]:
    if maximum_runtime == 0:
        return lambda *_: True

    start_time = time.monotonic() * 1000
    return lambda *_: (time.monotonic() * 1000) - start_time < maximum_runtime

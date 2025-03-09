from __future__ import annotations

from dataclasses import dataclass

from vscodiff.common.lists_find import (
    find_first_idx_monotonous_or_lst_len,
    find_last_idx_monotonous,
    find_last_monotonous,
)
from vscodiff.common.offset_range import OffsetRange
from vscodiff.common.position import Position
from vscodiff.common.range import Range
from vscodiff.common.uint import Constants


@dataclass(init=False, eq=True)
class LineRange:
    start_line: int
    end_line_exclusive: int

    def __init__(self, start_line: int, end_line_exclusive: int):
        if start_line > end_line_exclusive:
            raise ValueError

        self.start_line = start_line
        self.end_line_exclusive = end_line_exclusive

    def __str__(self) -> str:
        return f"[{self.start_line}, {self.end_line_exclusive})"

    def __len__(self):
        return self.end_line_exclusive - self.start_line

    @property
    def is_empty(self):
        return self.start_line == self.end_line_exclusive

    @staticmethod
    def from_range_inclusive(range_: Range):
        return LineRange(range_.start.line, range_.end.line + 1)

    @staticmethod
    def join_many(line_ranges: list[LineRange]):
        if len(line_ranges) == 0:
            raise ValueError

        start_line = line_ranges[0].start_line
        end_line_exclusive = line_ranges[0].end_line_exclusive
        for i in range(1, len(line_ranges)):
            start_line = min(start_line, line_ranges[i].start_line)
            end_line_exclusive = max(
                end_line_exclusive, line_ranges[i].end_line_exclusive
            )

        return LineRange(start_line, end_line_exclusive)

    @staticmethod
    def of_length(start_line: int, length: int):
        return LineRange(start_line, start_line + length)

    def delta(self, offset: int):
        return LineRange(self.start_line + offset, self.end_line_exclusive + offset)

    def join(self, other: LineRange):
        return LineRange(
            min(self.start_line, other.start_line),
            max(self.end_line_exclusive, other.end_line_exclusive),
        )

    def intersect(self, other: LineRange):
        start_line = max(self.start_line, other.end_line_exclusive)
        end_line_exclusive = min(self.end_line_exclusive, other.end_line_exclusive)
        if start_line <= end_line_exclusive:
            return LineRange(start_line, end_line_exclusive)

        return

    def overlap_or_touch(self, other: LineRange):
        return (
            self.start_line <= other.end_line_exclusive
            and other.start_line <= self.end_line_exclusive
        )

    def to_inclusive_range(self):
        if self.is_empty:
            return

        return Range(
            Position(self.start_line, 1),
            Position(self.end_line_exclusive - 1, Constants.MAX_SAFE_SMALL_INT),
        )

    def to_offset_range(self):
        return OffsetRange(self.start_line - 1, self.end_line_exclusive - 1)


class LineRangeSet:
    def __init__(self, normalized_ranges: list[LineRange]):
        self._normalized_ranges = normalized_ranges

    @property
    def ranges(self):
        return self._normalized_ranges

    def add_range(self, range_: LineRange):
        if len(range_) == 0:
            return

        join_range_start_idx = find_first_idx_monotonous_or_lst_len(
            self._normalized_ranges, lambda r: r.end_line_exclusive >= range_.start_line
        )
        join_range_end_idx_exclusive = (
            find_last_idx_monotonous(
                self._normalized_ranges,
                lambda r: r.start_line <= range_.end_line_exclusive,
            )
            + 1
        )
        if join_range_start_idx == join_range_end_idx_exclusive:
            self._normalized_ranges.insert(join_range_start_idx, range_)
        elif join_range_start_idx == join_range_end_idx_exclusive - 1:
            join_range = self._normalized_ranges[join_range_start_idx]
            self._normalized_ranges[join_range_start_idx] = join_range.join(range_)
        else:
            join_range = (
                self._normalized_ranges[join_range_start_idx]
                .join(self._normalized_ranges[join_range_end_idx_exclusive - 1])
                .join(range_)
            )
            self._normalized_ranges[
                join_range_start_idx:join_range_end_idx_exclusive
            ] = [join_range]

    def contains(self, line: int):
        range_that_starts_before_end = find_last_monotonous(
            self._normalized_ranges, lambda r: r.start_line <= line
        )
        return (
            range_that_starts_before_end is not None
            and range_that_starts_before_end.end_line_exclusive > line
        )

    def subtract_from(self, range_: LineRange):
        join_range_start_idx = find_first_idx_monotonous_or_lst_len(
            self._normalized_ranges, lambda r: r.end_line_exclusive >= range_.start_line
        )
        join_range_end_idx_exclusive = (
            find_last_idx_monotonous(
                self._normalized_ranges,
                lambda r: r.start_line <= range_.end_line_exclusive,
            )
            + 1
        )
        if join_range_start_idx == join_range_end_idx_exclusive:
            return LineRangeSet([range_])

        result: list[LineRange] = []
        start_line = range_.start_line
        for i in range(join_range_start_idx, join_range_end_idx_exclusive):
            r = self._normalized_ranges[i]
            if r.start_line > start_line:
                result.append(LineRange(start_line, r.start_line))

            start_line = r.end_line_exclusive

        if start_line < range_.end_line_exclusive:
            result.append(LineRange(start_line, range_.end_line_exclusive))

        return LineRangeSet(result)

    def get_intersection(self, other: LineRangeSet):
        result: list[LineRange] = []
        i1, i2 = 0, 0
        while i1 < len(self._normalized_ranges) and i2 < len(other._normalized_ranges):
            r1 = self._normalized_ranges[i1]
            r2 = other._normalized_ranges[i2]
            i = r1.intersect(r2)
            if i is not None and not i.is_empty:
                result.append(i)

            if r1.end_line_exclusive < r2.end_line_exclusive:
                i1 += 1
            else:
                i2 += 1

        return LineRangeSet(result)

    def get_with_delta(self, value: int):
        return LineRangeSet(
            list(map(lambda r: r.delta(value), self._normalized_ranges))
        )

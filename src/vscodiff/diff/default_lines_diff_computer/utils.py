from __future__ import annotations

from vscodiff.common.char_code import CharCode
from vscodiff.common.line_range import LineRange
from vscodiff.diff.range_mapping import DetailedLineRangeMapping


class Array2D[T]:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._array: list[T] = [None] * (width * height)  # type: ignore

    def get(self, x: int, y: int) -> T:
        return self._array[x + y * self.width]

    def set(self, x: int, y: int, value: T) -> None:
        self._array[x + y * self.width] = value


def is_space(char_code: int) -> bool:
    return char_code == CharCode.SPACE or char_code == CharCode.TAB


class LineRangeFragment:
    _chr_keys: dict[str, int] = {}

    @staticmethod
    def _get_key(chr_: str) -> int:
        key = LineRangeFragment._chr_keys.get(chr_)
        if key is None:
            key = len(LineRangeFragment._chr_keys)
            LineRangeFragment._chr_keys[chr_] = key

        return key

    def __init__(
        self,
        range_: LineRange,
        lines: list[str],
        source: DetailedLineRangeMapping,
    ):
        self.range = range_
        self.lines = lines
        self.source = source
        self._histogram: list[int] = []

        counter = 0
        for i in range(range_.start_line - 1, range_.end_line_exclusive - 1):
            line = lines[i]
            for j in range(len(line)):
                counter += 1
                key = LineRangeFragment._get_key(line[j])
                while len(self._histogram) <= key:
                    self._histogram.append(0)

                self._histogram[key] += 1

            counter += 1
            key = LineRangeFragment._get_key("\n")
            while len(self._histogram) <= key:
                self._histogram.append(0)

            self._histogram[key] += 1

        self._total_count = counter

    def compute_similarity(self, other: LineRangeFragment) -> float:
        sum_differences = 0
        max_length = max(len(self._histogram), len(other._histogram))
        for i in range(max_length):
            a = self._histogram[i] if i < len(self._histogram) else 0
            b = other._histogram[i] if i < len(other._histogram) else 0
            sum_differences += abs(a - b)

        return 1 - sum_differences / (self._total_count + other._total_count)

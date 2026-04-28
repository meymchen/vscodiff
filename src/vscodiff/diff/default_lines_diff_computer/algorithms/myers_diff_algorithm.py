from __future__ import annotations

from vscodiff.common.offset_range import OffsetRange
from vscodiff.diff.default_lines_diff_computer.algorithms.diff_algorithm import (
    DiffAlgorithm,
    DiffAlgorithmResult,
    InfiniteTimeout,
    Sequence,
    SequenceDiff,
    Timeout,
)


class MyersDiffAlgorithm(DiffAlgorithm):
    def compute(
        self,
        seq1: Sequence,
        seq2: Sequence,
        timeout: Timeout | None = None,
    ) -> DiffAlgorithmResult:
        if timeout is None:
            timeout = InfiniteTimeout.instance

        if seq1.length == 0 or seq2.length == 0:
            return DiffAlgorithmResult.trivial(seq1, seq2)

        seq_x = seq1
        seq_y = seq2

        def get_x_after_snake(x: int, y: int) -> int:
            while (
                x < seq_x.length
                and y < seq_y.length
                and seq_x.get_element(x) == seq_y.get_element(y)
            ):
                x += 1
                y += 1

            return x

        d = 0
        v = _FastInt32Array()
        v.set(0, get_x_after_snake(0, 0))

        paths: _FastArrayNegativeIndices[_SnakePath | None] = (
            _FastArrayNegativeIndices()
        )
        paths.set(0, None if v.get(0) == 0 else _SnakePath(None, 0, 0, v.get(0)))

        k = 0

        while True:
            d += 1
            if not timeout.is_valid():
                return DiffAlgorithmResult.trivial_timeout(seq_x, seq_y)

            lower_bound = -min(d, seq_y.length + (d % 2))
            upper_bound = min(d, seq_x.length + (d % 2))
            broke = False
            for k in range(lower_bound, upper_bound + 1, 2):
                max_x_of_d_line_top = -1 if k == upper_bound else v.get(k + 1)
                max_x_of_d_line_left = -1 if k == lower_bound else v.get(k - 1) + 1
                x = min(max(max_x_of_d_line_top, max_x_of_d_line_left), seq_x.length)
                y = x - k
                if x > seq_x.length or y > seq_y.length:
                    continue

                new_max_x = get_x_after_snake(x, y)
                v.set(k, new_max_x)
                last_path = (
                    paths.get(k + 1) if x == max_x_of_d_line_top else paths.get(k - 1)
                )
                paths.set(
                    k,
                    _SnakePath(last_path, x, y, new_max_x - x)
                    if new_max_x != x
                    else last_path,
                )

                if v.get(k) == seq_x.length and v.get(k) - k == seq_y.length:
                    broke = True
                    break

            if broke:
                break

        path = paths.get(k)
        result: list[SequenceDiff] = []
        last_aligning_pos_s1 = seq_x.length
        last_aligning_pos_s2 = seq_y.length

        while True:
            end_x = path.x + path.length if path else 0
            end_y = path.y + path.length if path else 0

            if end_x != last_aligning_pos_s1 or end_y != last_aligning_pos_s2:
                result.append(
                    SequenceDiff(
                        OffsetRange(end_x, last_aligning_pos_s1),
                        OffsetRange(end_y, last_aligning_pos_s2),
                    )
                )

            if not path:
                break

            last_aligning_pos_s1 = path.x
            last_aligning_pos_s2 = path.y

            path = path.prev

        result.reverse()
        return DiffAlgorithmResult(result, False)


class _SnakePath:
    def __init__(
        self,
        prev: _SnakePath | None,
        x: int,
        y: int,
        length: int,
    ):
        self.prev = prev
        self.x = x
        self.y = y
        self.length = length


class _FastInt32Array:
    def __init__(self):
        self._positive_arr: list[int] = [0] * 10
        self._negative_arr: list[int] = [0] * 10

    def get(self, idx: int) -> int:
        if idx < 0:
            idx = -idx - 1
            return self._negative_arr[idx]

        return self._positive_arr[idx]

    def set(self, idx: int, value: int) -> None:
        if idx < 0:
            idx = -idx - 1
            if idx >= len(self._negative_arr):
                self._negative_arr.extend([0] * len(self._negative_arr))

            self._negative_arr[idx] = value
        else:
            if idx >= len(self._positive_arr):
                self._positive_arr.extend([0] * len(self._positive_arr))

            self._positive_arr[idx] = value


class _FastArrayNegativeIndices[T]:
    def __init__(self):
        self._positive_arr: list[T] = []
        self._negative_arr: list[T] = []

    def get(self, idx: int) -> T:
        if idx < 0:
            idx = -idx - 1
            return self._negative_arr[idx]

        return self._positive_arr[idx]

    def set(self, idx: int, value: T) -> None:
        if idx < 0:
            idx = -idx - 1
            while len(self._negative_arr) <= idx:
                self._negative_arr.append(None)  # type: ignore

            self._negative_arr[idx] = value
        else:
            while len(self._positive_arr) <= idx:
                self._positive_arr.append(None)  # type: ignore

            self._positive_arr[idx] = value

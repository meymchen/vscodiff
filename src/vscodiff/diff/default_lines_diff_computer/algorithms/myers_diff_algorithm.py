from __future__ import annotations

import math

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

        found, path = self._find_final_snake_path(seq1, seq2, timeout)
        if not found:
            return DiffAlgorithmResult.trivial_timeout(seq1, seq2)

        result = self._build_diffs(path, seq1.length, seq2.length)
        return DiffAlgorithmResult(result, False)

    def _find_final_snake_path(
        self,
        seq_x: Sequence,
        seq_y: Sequence,
        timeout: Timeout,
    ) -> tuple[bool, _SnakePath | None]:
        # Run the O(ND) search. Returns (True, final path) once the end of
        # both sequences is reached, or (False, None) on timeout. The path may
        # legitimately be None (no snake recorded on the final diagonal).
        d = 0
        v = _FastInt32Array()
        v.set(0, self._get_x_after_snake(seq_x, seq_y, 0, 0))

        paths: _FastArrayNegativeIndices[_SnakePath | None] = (
            _FastArrayNegativeIndices()
        )
        paths.set(0, None if v.get(0) == 0 else _SnakePath(None, 0, 0, v.get(0)))

        while True:
            d += 1
            if not timeout.is_valid():
                return False, None

            lower_bound = -min(d, seq_y.length + (d % 2))
            upper_bound = min(d, seq_x.length + (d % 2))
            for k in range(lower_bound, upper_bound + 1, 2):
                if self._extend_snake_at_k(
                    seq_x, seq_y, v, paths, k, lower_bound, upper_bound
                ):
                    return True, paths.get(k)

    def _extend_snake_at_k(
        self,
        seq_x: Sequence,
        seq_y: Sequence,
        v: _FastInt32Array,
        paths: _FastArrayNegativeIndices[_SnakePath | None],
        k: int,
        lower_bound: int,
        upper_bound: int,
    ) -> bool:
        # Advance diagonal k by one d-step. Returns True once the end of both
        # sequences is reached, False otherwise (including when this diagonal
        # runs out of bounds and must be skipped).
        max_x_of_d_line_top = -1 if k == upper_bound else v.get(k + 1)
        max_x_of_d_line_left = -1 if k == lower_bound else v.get(k - 1) + 1
        if max_x_of_d_line_top is None:
            # JS Math.max(undefined, ...) is NaN, and so is x below.
            x = math.nan
        else:
            x = min(max(max_x_of_d_line_top, max_x_of_d_line_left), seq_x.length)
        y = x - k
        if x > seq_x.length or y > seq_y.length:
            return False

        new_max_x = self._get_x_after_snake(seq_x, seq_y, x, y)
        v.set(k, new_max_x)
        last_path = paths.get(k + 1) if x == max_x_of_d_line_top else paths.get(k - 1)
        paths.set(
            k,
            _SnakePath(last_path, x, y, new_max_x - x) if new_max_x != x else last_path,
        )

        return v.get(k) == seq_x.length and v.get(k) - k == seq_y.length

    def _get_x_after_snake(
        self, seq_x: Sequence, seq_y: Sequence, x: int, y: int
    ) -> int:
        while x < seq_x.length and y < seq_y.length:
            # Mirror JS semantics: a negative index reads undefined (None
            # here), and undefined === undefined is true.
            ex = seq_x.get_element(x) if x >= 0 else None
            ey = seq_y.get_element(y) if y >= 0 else None
            if ex is None and ey is None:
                pass
            elif ex is None or ey is None:
                break
            elif ex != ey:
                break
            x += 1
            y += 1

        return x

    def _build_diffs(
        self, path: _SnakePath | None, len_x: int, len_y: int
    ) -> list[SequenceDiff]:
        # Walk the snake path backwards, collecting the diff ranges between
        # aligning positions, then reverse into forward order.
        result: list[SequenceDiff] = []
        last_aligning_pos_s1 = len_x
        last_aligning_pos_s2 = len_y

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
        return result


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
            if idx >= len(self._negative_arr):
                # Mirror JS semantics: an out-of-bounds read on a TypedArray
                # yields undefined (None here) instead of raising.
                return None  # type: ignore
            return self._negative_arr[idx]

        if idx >= len(self._positive_arr):
            return None  # type: ignore
        return self._positive_arr[idx]

    def set(self, idx: int, value: int) -> None:
        # Mirror JS semantics: an Int32Array stores NaN as 0.
        if math.isnan(value):
            value = 0
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
            # Mirror JS semantics: reading an index that was never set yields
            # undefined (None here) instead of raising.
            if idx >= len(self._negative_arr):
                return None  # type: ignore
            return self._negative_arr[idx]

        if idx >= len(self._positive_arr):
            return None  # type: ignore
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

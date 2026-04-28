from __future__ import annotations

from typing import Callable

from vscodiff.common.offset_range import OffsetRange
from vscodiff.diff.default_lines_diff_computer.algorithms.diff_algorithm import (
    DiffAlgorithm,
    DiffAlgorithmResult,
    InfiniteTimeout,
    Sequence,
    SequenceDiff,
    Timeout,
)
from vscodiff.diff.default_lines_diff_computer.utils import Array2D


class DynamicProgrammingDiffing(DiffAlgorithm):
    def compute(
        self,
        seq1: Sequence,
        seq2: Sequence,
        timeout: Timeout | None = None,
        equality_score: Callable[[int, int], float] | None = None,
    ) -> DiffAlgorithmResult:
        if timeout is None:
            timeout = InfiniteTimeout.instance

        if seq1.length == 0 or seq2.length == 0:
            return DiffAlgorithmResult.trivial(seq1, seq2)

        lcs_lengths = Array2D[float](seq1.length, seq2.length)
        directions = Array2D[int](seq1.length, seq2.length)
        lengths = Array2D[int](seq1.length, seq2.length)

        for s1 in range(seq1.length):
            for s2 in range(seq2.length):
                if not timeout.is_valid():
                    return DiffAlgorithmResult.trivial_timeout(seq1, seq2)

                horizontal_len = 0 if s1 == 0 else lcs_lengths.get(s1 - 1, s2)
                vertical_len = 0 if s2 == 0 else lcs_lengths.get(s1, s2 - 1)

                if seq1.get_element(s1) == seq2.get_element(s2):
                    if s1 == 0 or s2 == 0:
                        extended_seq_score: float = 0
                    else:
                        extended_seq_score = lcs_lengths.get(s1 - 1, s2 - 1)

                    if s1 > 0 and s2 > 0 and directions.get(s1 - 1, s2 - 1) == 3:
                        extended_seq_score += lengths.get(s1 - 1, s2 - 1)

                    extended_seq_score += (
                        equality_score(s1, s2) if equality_score else 1
                    )
                else:
                    extended_seq_score = -1

                new_value = max(horizontal_len, vertical_len, extended_seq_score)

                if new_value == extended_seq_score:
                    prev_len = lengths.get(s1 - 1, s2 - 1) if s1 > 0 and s2 > 0 else 0
                    lengths.set(s1, s2, prev_len + 1)
                    directions.set(s1, s2, 3)
                elif new_value == horizontal_len:
                    lengths.set(s1, s2, 0)
                    directions.set(s1, s2, 1)
                elif new_value == vertical_len:
                    lengths.set(s1, s2, 0)
                    directions.set(s1, s2, 2)

                lcs_lengths.set(s1, s2, new_value)

        result: list[SequenceDiff] = []
        last_aligning_pos_s1 = seq1.length
        last_aligning_pos_s2 = seq2.length

        def report_decreasing_aligning_positions(s1: int, s2: int) -> None:
            nonlocal last_aligning_pos_s1, last_aligning_pos_s2
            if s1 + 1 != last_aligning_pos_s1 or s2 + 1 != last_aligning_pos_s2:
                result.append(
                    SequenceDiff(
                        OffsetRange(s1 + 1, last_aligning_pos_s1),
                        OffsetRange(s2 + 1, last_aligning_pos_s2),
                    )
                )

            last_aligning_pos_s1 = s1
            last_aligning_pos_s2 = s2

        s1 = seq1.length - 1
        s2 = seq2.length - 1
        while s1 >= 0 and s2 >= 0:
            if directions.get(s1, s2) == 3:
                report_decreasing_aligning_positions(s1, s2)
                s1 -= 1
                s2 -= 1
            else:
                if directions.get(s1, s2) == 1:
                    s1 -= 1
                else:
                    s2 -= 1

        report_decreasing_aligning_positions(-1, -1)
        result.reverse()
        return DiffAlgorithmResult(result, False)

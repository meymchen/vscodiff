from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from vscodiff.common.lists import for_each_adjacent
from vscodiff.common.offset_range import OffsetRange
from vscodiff.common.uint import Constants


class DiffAlgorithm(ABC):
    @abstractmethod
    def compute(
        self, seq1: Sequence, seq2: Sequence, timeout: Timeout | None = None
    ) -> DiffAlgorithmResult:
        raise NotImplementedError


class Sequence(ABC):
    @property
    @abstractmethod
    def length(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_element(self, offset: int) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_boundary_score(self, length: int) -> int: ...

    @abstractmethod
    def is_strongly_equal(self, offset1: int, offset2: int) -> bool:
        raise NotImplementedError


class Timeout(ABC):
    @abstractmethod
    def is_valid(self) -> bool:
        raise NotImplementedError


@dataclass
class DiffAlgorithmResult:
    diffs: list[SequenceDiff]
    hit_timeout: bool

    @staticmethod
    def trivial(seq1: Sequence, seq2: Sequence) -> DiffAlgorithmResult:
        return DiffAlgorithmResult(
            [
                SequenceDiff(
                    OffsetRange.of_length(seq1.length),
                    OffsetRange.of_length(seq2.length),
                )
            ],
            False,
        )

    @staticmethod
    def trivial_timeout(seq1: Sequence, seq2: Sequence) -> DiffAlgorithmResult:
        return DiffAlgorithmResult(
            [
                SequenceDiff(
                    OffsetRange.of_length(seq1.length),
                    OffsetRange.of_length(seq2.length),
                )
            ],
            True,
        )


@dataclass
class SequenceDiff:
    seq1_range: OffsetRange
    seq2_range: OffsetRange

    @staticmethod
    def invert(
        sequence_diffs: list[SequenceDiff], doc_length: int
    ) -> list[SequenceDiff]:
        result: list[SequenceDiff] = []
        for_each_adjacent(
            sequence_diffs,
            lambda a, b: result.append(
                SequenceDiff.from_offset_pairs(
                    a.get_end_exclusive() if a is not None else OffsetPair.zero(),
                    b.get_starts()
                    if b is not None
                    else OffsetPair(
                        doc_length,
                        (
                            a.seq2_range.end_exclusive - a.seq1_range.end_exclusive
                            if a is not None
                            else 0
                        )
                        + doc_length,
                    ),
                )
            ),
        )
        return result

    @staticmethod
    def from_offset_pairs(start: OffsetPair, end_exclusive: OffsetPair) -> SequenceDiff:
        return SequenceDiff(
            OffsetRange(start.offset1, end_exclusive.offset1),
            OffsetRange(start.offset2, end_exclusive.offset2),
        )

    @staticmethod
    def assert_sorted(sequence_diffs: list[SequenceDiff]):
        last: SequenceDiff | None = None
        for cur in sequence_diffs:
            if last is not None:
                if not (
                    last.seq1_range.end_exclusive <= cur.seq1_range.start
                    and last.seq2_range.end_exclusive <= cur.seq2_range.start
                ):
                    raise ValueError

            last = cur

    def swap(self):
        return SequenceDiff(self.seq2_range, self.seq1_range)

    def join(self, other: SequenceDiff):
        return SequenceDiff(
            self.seq1_range.join(other.seq1_range),
            self.seq2_range.join(other.seq2_range),
        )

    def delta(self, offset: int):
        if offset == 0:
            return self

        return SequenceDiff(
            self.seq1_range.delta(offset), self.seq2_range.delta(offset)
        )

    def delta_start(self, offset: int) -> SequenceDiff:
        if offset == 0:
            return self

        return SequenceDiff(
            self.seq1_range.delta_start(offset), self.seq2_range.delta_start(offset)
        )

    def delta_end(self, offset: int) -> SequenceDiff:
        if offset == 0:
            return self

        return SequenceDiff(
            self.seq1_range.delta_end(offset), self.seq2_range.delta_end(offset)
        )

    def intersects_or_touches(self, other: SequenceDiff) -> bool:
        return self.seq1_range.intersects_or_touches(
            other.seq1_range
        ) or self.seq2_range.intersects_or_touches(other.seq2_range)

    def intersect(self, other: SequenceDiff):
        i1 = self.seq1_range.intersect(other.seq1_range)
        i2 = self.seq2_range.intersect(other.seq2_range)
        if not i1 or not i2:
            return

        return SequenceDiff(i1, i2)

    def get_starts(self) -> OffsetPair:
        return OffsetPair(self.seq1_range.start, self.seq2_range.start)

    def get_end_exclusive(self) -> OffsetPair:
        return OffsetPair(self.seq1_range.end_exclusive, self.seq2_range.end_exclusive)


@dataclass(eq=True)
class OffsetPair:
    offset1: int
    offset2: int

    @staticmethod
    def zero():
        return OffsetPair(0, 0)

    @staticmethod
    def max():
        return OffsetPair(Constants.MAX_SAFE_SMALL_INT, Constants.MAX_SAFE_SMALL_INT)

    def delta(self, offset: int):
        if offset == 0:
            return self

        return OffsetPair(self.offset1 + offset, self.offset2 + offset)

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(init=False, eq=True)
class OffsetRange:
    start: int
    end_exclusive: int

    def __init__(self, start: int, end_exclusive: int):
        if start > end_exclusive:
            raise ValueError

        self.start = start
        self.end_exclusive = end_exclusive

    def __str__(self) -> str:
        return f"[{self.start}, {self.end_exclusive})"

    def __len__(self):
        return self.end_exclusive - self.start

    @property
    def is_empty(self):
        return self.start == self.end_exclusive

    @staticmethod
    def of_length(length: int):
        return OffsetRange(0, length)

    @staticmethod
    def of_start_and_length(start: int, length: int):
        return OffsetRange(start, start + length)

    @staticmethod
    def empty_at(offset: int):
        return OffsetRange(offset, offset)

    def delta(self, offset: int):
        return OffsetRange(self.start + offset, self.end_exclusive + offset)

    def delta_start(self, offset: int):
        return OffsetRange(self.start + offset, self.end_exclusive)

    def delta_end(self, offset: int):
        return OffsetRange(self.start, self.end_exclusive + offset)

    def join(self, other: OffsetRange):
        return OffsetRange(
            min(self.start, other.start), max(self.end_exclusive, other.end_exclusive)
        )

    def intersect(self, other: OffsetRange):
        start = max(self.start, other.start)
        end = min(self.end_exclusive, other.end_exclusive)
        if start <= end:
            return OffsetRange(start, end)

        return

    def intersects(self, other: OffsetRange):
        start = max(self.start, other.start)
        end = min(self.end_exclusive, other.end_exclusive)
        return start < end

    def intersects_or_touches(self, other: OffsetRange):
        start = max(self.start, other.start)
        end = min(self.end_exclusive, other.end_exclusive)
        return start <= end

    def slice[T](self, lst: list[T]):
        return lst[self.start : self.end_exclusive]

    def substring(self, source: str):
        return source[self.start : self.end_exclusive]

    def for_each(self, f: Callable[[int], None]):
        for i in range(self.start, self.end_exclusive):
            f(i)

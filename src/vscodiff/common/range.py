from __future__ import annotations

from dataclasses import dataclass
from typing import overload

from vscodiff.common.position import Position


@dataclass(init=False, eq=True)
class Range:
    start: Position
    end: Position

    @overload
    def __init__(self, a: Position, b: Position) -> None: ...

    @overload
    def __init__(self, a: int, b: int, c: int, d: int) -> None: ...

    def __init__(
        self,
        a: Position | int,
        b: Position | int,
        c: int | None = None,
        d: int | None = None,
    ) -> None:
        if isinstance(a, Position) and isinstance(b, Position):
            start, end = a, b
        else:
            assert isinstance(a, int) and isinstance(b, int)
            assert c is not None and d is not None
            start = Position(a, b)
            end = Position(c, d)

        if start > end:
            self.start = end
            self.end = start
        else:
            self.start = start
            self.end = end

    def __str__(self) -> str:
        return f"[{self.start.line}, {self.start.column} -> {self.end.line}, {self.end.column}]"

    @property
    def start_line(self) -> int:
        return self.start.line

    @property
    def start_column(self) -> int:
        return self.start.column

    @property
    def end_line(self) -> int:
        return self.end.line

    @property
    def end_column(self) -> int:
        return self.end.column

    def is_empty(self):
        return self.start == self.end

    def get_start_position(self) -> Position:
        return self.start

    def get_end_position(self) -> Position:
        return self.end

    def union(self, other: Range):
        return Range(min(self.start, other.start), max(self.end, other.end))

    def plus_range(self, other: Range) -> Range:
        return self.union(other)

    @staticmethod
    def from_positions(start: Position, end: Position | None = None) -> Range:
        if end is None:
            end = start
        return Range(start, end)

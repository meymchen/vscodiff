from __future__ import annotations

from dataclasses import dataclass

from vscodiff.common.position import Position


@dataclass(init=False, eq=True)
class Range:
    start: Position
    end: Position

    def __init__(self, start: Position, end: Position):
        if start > end:
            self.start = end
            self.end = start
        else:
            self.start = start
            self.end = end

    def __str__(self) -> str:
        return f"[{self.start.line}, {self.start.column} -> {self.end.line}, {self.end.column}]"

    def is_empty(self):
        return self.start == self.end

    def union(self, other: Range):
        return Range(min(self.start, other.start), max(self.end, other.end))

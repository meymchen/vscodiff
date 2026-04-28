from __future__ import annotations

from dataclasses import dataclass


@dataclass(eq=True, order=True)
class Position:
    line: int
    """line number (starts at 1)"""
    column: int
    """column (the first character in a line is between column 1 and column 2)"""

    def __str__(self):
        return f"({self.line}, {self.column})"

    def is_before(self, other: Position) -> bool:
        if self.line < other.line:
            return True

        if other.line < self.line:
            return False

        return self.column < other.column

    def is_before_or_equal(self, other: Position) -> bool:
        if self.line < other.line:
            return True

        if other.line < self.line:
            return False

        return self.column <= other.column

    def delta(self, delta_line: int = 0, delta_column: int = 0) -> Position:
        return Position(
            max(1, self.line + delta_line), max(1, self.column + delta_column)
        )

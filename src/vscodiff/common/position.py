from dataclasses import dataclass


@dataclass(eq=True, order=True)
class Position:
    line: int
    """line number (starts at 1)"""
    column: int
    """column (the first character in a line is between column 1 and column 2)"""

    def __str__(self):
        return f"({self.line}, {self.column})"

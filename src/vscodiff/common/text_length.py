from dataclasses import dataclass

from vscodiff.common.line_range import LineRange
from vscodiff.common.position import Position
from vscodiff.common.range import Range


@dataclass(eq=True)
class TextLength:
    line_count: int
    column_count: int

    @staticmethod
    def between_positions(pos1: Position, pos2: Position):
        if pos1.line == pos2.line:
            return TextLength(0, pos2.column - pos1.column)
        else:
            return TextLength(pos2.line - pos1.line, pos2.column - 1)

    @staticmethod
    def of_range(range_: Range):
        return TextLength.between_positions(range_.start, range_.end)

    @staticmethod
    def of_text(text: str):
        line, column = 0, 0
        for ch in text:
            if ch == "\n":
                line += 1
                column = 0
            else:
                column += 1

        return TextLength(line, column)

    def create_range(self, start: Position):
        if self.line_count == 0:
            return Range(start, Position(start.line, start.column + self.column_count))

        else:
            return Range(
                start, Position(start.line + self.line_count, self.column_count + 1)
            )

    def to_range(self):
        return Range(
            Position(1, 1), Position(self.line_count + 1, self.column_count + 1)
        )

    def to_line_range(self):
        return LineRange.of_length(1, self.line_count + 1)

    def add_to_position(self, pos: Position):
        if self.line_count == 0:
            return Position(pos.line, pos.column + self.column_count)
        else:
            return Position(pos.line + self.line_count, self.column_count + 1)

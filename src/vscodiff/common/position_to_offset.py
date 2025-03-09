from vscodiff.common.lists_find import find_last_idx_monotonous
from vscodiff.common.offset_range import OffsetRange
from vscodiff.common.position import Position
from vscodiff.common.range import Range
from vscodiff.common.text_length import TextLength


class PositionOffsetTransformer:
    def __init__(self, text: str):
        self.text = text

        self._line_start_offset_by_line_idx: list[int] = [0]
        self._line_end_offset_by_line_idx: list[int] = []
        for i, ch in enumerate(text):
            if ch == "\n":
                self._line_start_offset_by_line_idx.append(i + 1)

            if i > 0 and text[i - 1] == "\r":
                self._line_end_offset_by_line_idx.append(i - 1)
            else:
                self._line_end_offset_by_line_idx.append(i)

        self._line_end_offset_by_line_idx.append(len(text))

    @property
    def text_length(self):
        line_idx = len(self._line_start_offset_by_line_idx) - 1
        return TextLength(
            line_idx, len(self.text) - self._line_start_offset_by_line_idx[line_idx]
        )

    def get_line_length(self, line: int):
        return (
            self._line_end_offset_by_line_idx[line - 1]
            - self._line_start_offset_by_line_idx[line - 1]
        )

    def get_offset(self, pos: Position):
        val_pos = self._validate_position(pos)
        return (
            self._line_start_offset_by_line_idx[val_pos.line - 1] + val_pos.column - 1
        )

    def get_offset_range(self, range_: Range):
        return OffsetRange(self.get_offset(range_.start), self.get_offset(range_.end))

    def get_position(self, offset: int):
        idx = find_last_idx_monotonous(
            self._line_start_offset_by_line_idx, lambda i: i <= offset
        )
        line = idx + 1
        column = offset - self._line_start_offset_by_line_idx[idx] + 1
        return Position(line, column)

    def get_range(self, offset_range: OffsetRange):
        return Range(
            self.get_position(offset_range.start),
            self.get_position(offset_range.end_exclusive),
        )

    def _validate_position(self, pos: Position):
        if pos.line < 1:
            return Position(1, 1)

        line_count = self.text_length.line_count + 1
        if pos.line > line_count:
            line_length = self.get_line_length(line_count)
            return Position(line_count, line_length + 1)

        if pos.column < 1:
            return Position(pos.line, 1)

        line_length = self.get_line_length(pos.line)
        if pos.column - 1 > line_length:
            return Position(pos.line, line_length + 1)

        return pos

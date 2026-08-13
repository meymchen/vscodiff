from abc import ABC, abstractmethod
from typing import Callable

from vscodiff.common.position import Position
from vscodiff.common.range import Range
from vscodiff.common.text_length import TextLength
from vscodiff.common.uint import Constants


class AbstractText(ABC):
    @abstractmethod
    def get_value_of_range(self, range_: Range) -> str: ...

    @property
    @abstractmethod
    def length(self) -> TextLength: ...

    def get_line_length(self, line: int):
        return len(
            self.get_value_of_range(
                Range(Position(line, 1), Position(line, Constants.MAX_SAFE_SMALL_INT))
            )
        )


class LineBasedText(AbstractText):
    def __init__(self, get_line_content: Callable[[int], str], line_count: int):
        assert line_count >= 1

        self._get_line_content = get_line_content
        self._line_count = line_count

        super().__init__()

    @property
    def length(self):
        last_line = self._get_line_content(self._line_count)
        return TextLength(self._line_count - 1, len(last_line))

    def get_value_of_range(self, range_: Range):
        if range_.start.line == range_.end.line:
            return self._get_line_content(range_.start.line)[
                range_.start.column - 1 : range_.end.column - 1
            ]

        result = self._get_line_content(range_.start.line)[range_.start.column - 1 :]
        for i in range(range_.start.line + 1, range_.end.line):
            result += "\n" + self._get_line_content(i)

        result += (
            "\n" + self._get_line_content(range_.end.line)[: range_.end.column - 1]
        )
        return result

    def get_line_length(self, line: int):
        return len(self._get_line_content(line))


class ListText(LineBasedText):
    def __init__(self, lines: list[str]):
        super().__init__(lambda n: lines[n - 1], len(lines))

from __future__ import annotations

from vscodiff.diff.default_lines_diff_computer.default_lines_diff_computer import (
    DefaultLineDiffComputer,
)
from vscodiff.diff.legacy_lines_diff_computer import LegacyLinesDiffComputer
from vscodiff.diff.lines_diff_computer import LinesDiffComputer


class LinesDiffComputers:
    @staticmethod
    def get_legacy() -> LinesDiffComputer:
        return LegacyLinesDiffComputer()

    @staticmethod
    def get_default() -> LinesDiffComputer:
        return DefaultLineDiffComputer()


lines_diff_computers = LinesDiffComputers()

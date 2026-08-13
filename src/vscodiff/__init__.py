"""vscodiff — Python implementation of VS Code's diff algorithm."""

from vscodiff.common.line_range import LineRange
from vscodiff.common.position import Position
from vscodiff.common.range import Range
from vscodiff.diff.lines_diff_computer import MovedText
from vscodiff.diff.range_mapping import (
    DetailedLineRangeMapping,
    LineRangeMapping,
    RangeMapping,
)
from vscodiff.engine import DiffOptions, DocumentDiff, VSCodeDiff, VSCodeDiffOptions

__all__ = [
    # Main entry
    "VSCodeDiff",
    "VSCodeDiffOptions",
    "DiffOptions",
    # Diff result types
    "DocumentDiff",
    "DetailedLineRangeMapping",
    "LineRangeMapping",
    "RangeMapping",
    "MovedText",
    # Primitives
    "LineRange",
    "Position",
    "Range",
]

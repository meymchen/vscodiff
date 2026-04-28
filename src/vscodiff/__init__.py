"""vscodiff — Python implementation of VS Code's diff algorithm."""

from vscodiff.engine import VSCDiff, VSCDiffOptions, DiffOptions
from vscodiff.common.diff.diff_change import DiffChange, DiffResult
from vscodiff.common.diff.diff import LcsDiff, Sequence, StringDiffSequence, string_diff
from vscodiff.common.line_range import LineRange
from vscodiff.common.position import Position
from vscodiff.common.range import Range
from vscodiff.common.text_edit import AbstractText
from vscodiff.diff.document_diff_provider import (
    DocumentDiff,
    DocumentDiffProvider,
    DocumentDiffProviderOptions,
    null_document_diff,
)
from vscodiff.diff.lines_diff_computer import (
    LinesDiff,
    LinesDiffComputer,
    LinesDiffComputerOptions,
    MovedText,
)
from vscodiff.diff.model import GetValueOptions, TextModel
from vscodiff.diff.range_mapping import (
    DetailedLineRangeMapping,
    LineRangeMapping,
    RangeMapping,
)

__all__ = [
    # Main entry
    "VSCDiff",
    "VSCDiffOptions",
    "DiffOptions",
    # Diff result types
    "DiffChange",
    "DiffResult",
    "DocumentDiff",
    "DetailedLineRangeMapping",
    "LineRangeMapping",
    "RangeMapping",
    "LinesDiff",
    "MovedText",
    # Interfaces
    "DocumentDiffProvider",
    "DocumentDiffProviderOptions",
    "LinesDiffComputer",
    "LinesDiffComputerOptions",
    "TextModel",
    "GetValueOptions",
    # Algorithm
    "LcsDiff",
    "Sequence",
    "StringDiffSequence",
    "string_diff",
    # Primitives
    "LineRange",
    "Position",
    "Range",
    "AbstractText",
    # Constants
    "null_document_diff",
]

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import NamedTuple

from vscodiff.diff.range_mapping import DetailedLineRangeMapping, LineRangeMapping


class LinesDiffComputer(ABC):
    @abstractmethod
    def compute_diff(
        self,
        original_lines: list[str],
        modified_lines: list[str],
        options: LinesDiffComputerOptions,
    ) -> LinesDiff:
        raise NotImplementedError


class LinesDiffComputerOptions(NamedTuple):
    ignore_trim_whitespace: bool
    max_computation_time_ms: int
    compute_moves: bool
    extend_to_subwords: bool | None


@dataclass
class LinesDiff:
    changes: list[DetailedLineRangeMapping]
    moves: list[MovedText]
    hit_timeout: bool


@dataclass
class MovedText:
    line_range_mapping: LineRangeMapping
    changes: list[DetailedLineRangeMapping]

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from vscodiff.diff.lines_diff_computer import MovedText
from vscodiff.diff.model import TextModel
from vscodiff.diff.range_mapping import DetailedLineRangeMapping


@dataclass
@dataclass
class DocumentDiffProviderOptions:
    ignore_trim_whitespace: bool = True
    max_computation_time_ms: int = 5000
    compute_moves: bool = False
    extend_to_subwords: bool | None = None


@dataclass
class DocumentDiff:
    identical: bool
    quit_early: bool
    changes: list[DetailedLineRangeMapping] = field(default_factory=list)
    moves: list[MovedText] = field(default_factory=list)


class DocumentDiffProvider(ABC):
    @abstractmethod
    async def compute_diff(
        self,
        original: TextModel,
        modified: TextModel,
        options: DocumentDiffProviderOptions,
    ) -> DocumentDiff:
        raise NotImplementedError


null_document_diff = DocumentDiff(
    identical=True,
    quit_early=False,
    changes=[],
    moves=[],
)

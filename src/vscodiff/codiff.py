from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from vscodiff.common.cache import LRUCache
from vscodiff.common.line_range import LineRange
from vscodiff.common.range import Range
from vscodiff.common.strings import split_lines
from vscodiff.diff.document_diff_provider import (
    DocumentDiff,
    DocumentDiffProviderOptions,
)
from vscodiff.diff.lines_diff_computer import LinesDiffComputerOptions
from vscodiff.diff.lines_diff_computers import lines_diff_computers
from vscodiff.diff.range_mapping import DetailedLineRangeMapping, RangeMapping

DiffAlgorithmName = Literal["legacy", "advanced"]


@dataclass
class DiffOptions(DocumentDiffProviderOptions):
    diff_algorithm: DiffAlgorithmName = "advanced"


@dataclass
class CodiffOptions:
    diff_options: DiffOptions = field(
        default_factory=lambda: DiffOptions(
            ignore_trim_whitespace=True,
            max_computation_time_ms=1000,
            compute_moves=False,
            extend_to_subwords=False,
            diff_algorithm="advanced",
        )
    )
    cache_size: int = 100


class Codiff:
    DEFAULT_CACHE_SIZE = 100
    DEFAULT_DIFF_OPTIONS = DiffOptions(
        ignore_trim_whitespace=True,
        max_computation_time_ms=1000,
        compute_moves=False,
        extend_to_subwords=False,
        diff_algorithm="advanced",
    )

    def __init__(self, options: CodiffOptions | None = None):
        if options is None:
            self._options = CodiffOptions(
                diff_options=replace(self.DEFAULT_DIFF_OPTIONS),
                cache_size=self.DEFAULT_CACHE_SIZE,
            )
        else:
            self._options = options

        self._diff_cache: LRUCache[str, DocumentDiff] = LRUCache(
            self._options.cache_size
        )

    def _get_diff_algorithm(self, name: DiffAlgorithmName | None = None):
        if name == "legacy":
            return lines_diff_computers.get_legacy()

        return lines_diff_computers.get_default()

    def _get_full_range(self, lines: list[str]) -> Range:
        return Range(1, 1, len(lines) + 1, len(lines[-1]) + 1)

    def get_content_key(self, content: str) -> str:
        return content

    def _get_diff_cache_key(self, original: str, modified: str) -> str:
        return (
            f"{self.get_content_key(original)}"
            f"-codiff-cache-key-"
            f"{self.get_content_key(modified)}"
        )

    def compute_diff(
        self,
        original: str,
        modified: str,
        options: DiffOptions | None = None,
    ) -> DocumentDiff:
        original_lines = split_lines(original)
        modified_lines = split_lines(modified)

        if len(original_lines) == 1 and len(original_lines[0]) == 0:
            if len(modified_lines) == 1 and len(modified_lines[0]) == 0:
                return DocumentDiff(
                    identical=True,
                    quit_early=False,
                    changes=[],
                    moves=[],
                )

            return DocumentDiff(
                identical=False,
                quit_early=False,
                changes=[
                    DetailedLineRangeMapping(
                        LineRange(1, 2),
                        LineRange(1, len(modified_lines) + 1),
                        [
                            RangeMapping(
                                self._get_full_range(original_lines),
                                self._get_full_range(modified_lines),
                            ),
                        ],
                    ),
                ],
                moves=[],
            )

        cache_key = self._get_diff_cache_key(original, modified)
        cached_result = self._diff_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        diff_options = options if options is not None else self._options.diff_options
        diff_algorithm = self._get_diff_algorithm(diff_options.diff_algorithm)
        result = diff_algorithm.compute_diff(
            original_lines,
            modified_lines,
            LinesDiffComputerOptions(
                ignore_trim_whitespace=diff_options.ignore_trim_whitespace,
                max_computation_time_ms=diff_options.max_computation_time_ms,
                compute_moves=diff_options.compute_moves,
                extend_to_subwords=diff_options.extend_to_subwords,
            ),
        )
        diff_result = DocumentDiff(
            identical=original == modified,
            quit_early=result.hit_timeout,
            changes=result.changes,
            moves=result.moves,
        )
        self._diff_cache.put(cache_key, diff_result)
        return diff_result

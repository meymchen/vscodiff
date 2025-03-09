from __future__ import annotations

from dataclasses import dataclass

from vscodiff.common.asserts import check_adjacent_items
from vscodiff.common.line_range import LineRange
from vscodiff.common.lists import group_adjacent_by
from vscodiff.common.position import Position
from vscodiff.common.range import Range
from vscodiff.common.text_edit import AbstractText
from vscodiff.common.uint import Constants


@dataclass
class LineRangeMapping:
    original: LineRange
    modified: LineRange

    def flip(self):
        return LineRangeMapping(self.modified, self.original)

    def join(self, other: LineRangeMapping):
        return LineRangeMapping(
            self.original.join(other.original), self.modified.join(other.modified)
        )

    def to_range_mapping(self, original: list[str], modified: list[str]):
        if _is_valid_line_number(
            self.original.end_line_exclusive, original
        ) and _is_valid_line_number(self.modified.end_line_exclusive, modified):
            return RangeMapping(
                Range(
                    Position(self.original.start_line, 1),
                    Position(self.original.end_line_exclusive, 1),
                ),
                Range(
                    Position(self.modified.start_line, 1),
                    Position(self.modified.end_line_exclusive, 1),
                ),
            )

        if not self.original.is_empty and not self.modified.is_empty:
            return RangeMapping(
                Range(
                    Position(self.original.start_line, 1),
                    _normalize_position(
                        Position(
                            self.original.end_line_exclusive - 1,
                            Constants.MAX_SAFE_SMALL_INT,
                        ),
                        original,
                    ),
                ),
                Range(
                    Position(self.modified.start_line, 1),
                    _normalize_position(
                        Position(
                            self.modified.end_line_exclusive - 1,
                            Constants.MAX_SAFE_SMALL_INT,
                        ),
                        modified,
                    ),
                ),
            )

        if self.original.start_line > 1 and self.modified.start_line > 1:
            return RangeMapping(
                Range(
                    _normalize_position(
                        Position(
                            self.original.start_line - 1,
                            Constants.MAX_SAFE_SMALL_INT,
                        ),
                        original,
                    ),
                    _normalize_position(
                        Position(
                            self.original.end_line_exclusive - 1,
                            Constants.MAX_SAFE_SMALL_INT,
                        ),
                        original,
                    ),
                ),
                Range(
                    _normalize_position(
                        Position(
                            self.modified.start_line - 1,
                            Constants.MAX_SAFE_SMALL_INT,
                        ),
                        modified,
                    ),
                    _normalize_position(
                        Position(
                            self.modified.end_line_exclusive - 1,
                            Constants.MAX_SAFE_SMALL_INT,
                        ),
                        modified,
                    ),
                ),
            )

        raise ValueError


@dataclass(init=False)
class DetailedLineRangeMapping(LineRangeMapping):
    original_range: LineRange
    modified_range: LineRange
    inner_changes: list[RangeMapping] | None

    def __init__(
        self,
        original_range: LineRange,
        modified_range: LineRange,
        inner_changes: list[RangeMapping] | None = None,
    ):
        super().__init__(original_range, modified_range)

        self.original_range = original_range
        self.modified_range = modified_range
        self.inner_changes = inner_changes

    def flip(self):
        return DetailedLineRangeMapping(
            self.modified,
            self.original,
            list(map(lambda c: c.flip(), self.inner_changes))
            if self.inner_changes is not None
            else None,
        )


@dataclass
class RangeMapping:
    original_range: Range
    modified_range: Range

    def flip(self):
        return RangeMapping(self.modified_range, self.original_range)


def line_range_mapping_from_range_mappings(
    alignments: list[RangeMapping],
    original_lines: AbstractText,
    modified_lines: AbstractText,
    dont_assert_start_line: bool = False,
):
    changes: list[DetailedLineRangeMapping] = []
    for g in group_adjacent_by(
        map(
            lambda a: _get_line_range_mapping(a, original_lines, modified_lines),
            alignments,
        ),
        lambda a1, a2: a1.original.overlap_or_touch(a2.original)
        or a1.modified.overlap_or_touch(a2.modified),
    ):
        first = g[0]
        last = g[-1]
        changes.append(
            DetailedLineRangeMapping(
                first.original.join(last.original),
                first.modified.join(last.modified),
                list(map(lambda a: a.inner_changes[0], g)),  # type: ignore
            )
        )

    def assert_fn():
        if not dont_assert_start_line and len(changes) > 0:
            if changes[0].modified.start_line != changes[0].original.start_line:
                return False

            if (
                modified_lines.length.line_count
                - changes[-1].modified.end_line_exclusive
                != original_lines.length.line_count
                - changes[-1].original.end_line_exclusive
            ):
                return False

        return check_adjacent_items(
            changes,
            lambda m1, m2: m2.original.start_line - m1.original.end_line_exclusive
            == m2.modified.start_line - m1.modified.end_line_exclusive
            and m1.original.end_line_exclusive < m2.original.start_line
            and m1.modified.end_line_exclusive < m2.modified.start_line,
        )

    assert assert_fn()
    return changes


def _normalize_position(pos: Position, content: list[str]) -> Position:
    if pos.line < 1:
        return Position(1, 1)

    if pos.line > len(content):
        return Position(len(content), len(content[-1]) + 1)

    line_content = content[pos.line - 1]
    if pos.column > len(line_content) + 1:
        return Position(pos.line, len(line_content) + 1)

    return pos


def _is_valid_line_number(line_number: int, lines: list[str]):
    return line_number >= 1 and line_number <= len(lines)


def _get_line_range_mapping(
    range_mapping: RangeMapping,
    original_lines: AbstractText,
    modified_lines: AbstractText,
):
    line_start_delta, line_end_delta = 0, 0
    if (
        range_mapping.modified_range.end.column == 1
        and range_mapping.original_range.end.column == 1
        and range_mapping.original_range.start.line + line_start_delta
        <= range_mapping.original_range.end.line
        and range_mapping.modified_range.start.line + line_start_delta
        <= range_mapping.modified_range.end.line
    ):
        line_end_delta = -1

    if (
        range_mapping.modified_range.start.column - 1
        >= modified_lines.get_line_length(range_mapping.modified_range.start.line)
        and range_mapping.original_range.start.column - 1
        >= original_lines.get_line_length(range_mapping.original_range.start.line)
        and range_mapping.original_range.start.line
        <= range_mapping.original_range.end.line + line_end_delta
        and range_mapping.modified_range.start.line
        <= range_mapping.modified_range.end.line + line_end_delta
    ):
        line_start_delta = 1

    original_line_range = LineRange(
        range_mapping.original_range.start.line + line_start_delta,
        range_mapping.original_range.end.line + 1 + line_end_delta,
    )
    modified_line_range = LineRange(
        range_mapping.modified_range.start.line + line_start_delta,
        range_mapping.modified_range.end.line + 1 + line_end_delta,
    )
    return DetailedLineRangeMapping(
        original_line_range, modified_line_range, [range_mapping]
    )

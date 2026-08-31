from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key
import math

from vscodiff.common.line_range import LineRange, LineRangeSet
from vscodiff.common.lists import (
    compare_by,
    number_comparator,
    push_many,
    reverse_order,
)
from vscodiff.common.lists_find import MonotonousList, find_last_monotonous
from vscodiff.common.map import SetMap
from vscodiff.common.range import Range
from vscodiff.diff.default_lines_diff_computer.algorithms.diff_algorithm import (
    SequenceDiff,
    Timeout,
)
from vscodiff.diff.default_lines_diff_computer.algorithms.myers_diff_algorithm import (
    MyersDiffAlgorithm,
)
from vscodiff.diff.default_lines_diff_computer.lines_slice_char_sequence import (
    LinesSliceCharSequence,
)
from vscodiff.diff.default_lines_diff_computer.utils import LineRangeFragment, is_space
from vscodiff.diff.range_mapping import DetailedLineRangeMapping, LineRangeMapping


def compute_moved_lines(
    changes: list[DetailedLineRangeMapping],
    original_lines: list[str],
    modified_lines: list[str],
    hashed_original_lines: list[int],
    hashed_modified_lines: list[int],
    timeout: Timeout,
) -> list[LineRangeMapping]:
    moves, excluded_changes = _compute_moves_from_simple_deletions_to_simple_insertions(
        changes, original_lines, modified_lines, timeout
    )

    if not timeout.is_valid():
        return []

    filtered_changes = [c for c in changes if id(c) not in excluded_changes]
    unchanged_moves = _compute_unchanged_moves(
        filtered_changes,
        hashed_original_lines,
        hashed_modified_lines,
        original_lines,
        modified_lines,
        timeout,
    )
    push_many(moves, unchanged_moves)

    moves = _join_close_consecutive_moves(moves)

    def is_long_enough(current: LineRangeMapping) -> bool:
        offset_range = current.original.to_offset_range()
        lines = [
            line.strip()
            for line in original_lines[offset_range.start : offset_range.end_exclusive]
        ]
        original_text = "\n".join(lines)
        return (
            len(original_text) >= 15 and sum(1 for line in lines if len(line) >= 2) >= 2
        )

    moves = [m for m in moves if is_long_enough(m)]
    moves = _remove_moves_in_same_diff(changes, moves)

    return moves


def _compute_moves_from_simple_deletions_to_simple_insertions(
    changes: list[DetailedLineRangeMapping],
    original_lines: list[str],
    modified_lines: list[str],
    timeout: Timeout,
) -> tuple[list[LineRangeMapping], set[int]]:
    moves: list[LineRangeMapping] = []

    deletions = [
        LineRangeFragment(c.original, original_lines, c)
        for c in changes
        if c.modified.is_empty and len(c.original) >= 3
    ]
    insertions = [
        LineRangeFragment(c.modified, modified_lines, c)
        for c in changes
        if c.original.is_empty and len(c.modified) >= 3
    ]

    excluded_changes: set[int] = set()

    for deletion in deletions:
        highest_similarity = -1.0
        best: LineRangeFragment | None = None
        for insertion in insertions:
            similarity = deletion.compute_similarity(insertion)
            if similarity > highest_similarity:
                highest_similarity = similarity
                best = insertion

        if highest_similarity > 0.9 and best is not None:
            insertions.remove(best)
            moves.append(LineRangeMapping(deletion.range, best.range))
            excluded_changes.add(id(deletion.source))
            excluded_changes.add(id(best.source))

        if not timeout.is_valid():
            return moves, excluded_changes

    return moves, excluded_changes


@dataclass
class _PossibleMapping:
    modified_line_range: LineRange
    original_line_range: LineRange


def _compute_unchanged_moves(
    changes: list[DetailedLineRangeMapping],
    hashed_original_lines: list[int],
    hashed_modified_lines: list[int],
    original_lines: list[str],
    modified_lines: list[str],
    timeout: Timeout,
) -> list[LineRangeMapping]:
    original_3_line_hashes = _compute_original_3_line_hashes(
        changes, hashed_original_lines
    )

    changes.sort(
        key=cmp_to_key(compare_by(lambda c: c.modified.start_line, number_comparator))
    )

    possible_mappings = _find_possible_mappings(
        changes, hashed_modified_lines, original_3_line_hashes, timeout
    )
    if possible_mappings is None:
        return []

    moves, modified_set, original_set = _select_disjoint_mappings(possible_mappings)

    moves.sort(
        key=cmp_to_key(compare_by(lambda m: m.original.start_line, number_comparator))
    )

    monotonous_changes = MonotonousList(changes)
    for i in range(len(moves)):
        moves[i] = _extend_move(
            moves[i],
            monotonous_changes,
            changes,
            original_lines,
            modified_lines,
            original_set,
            modified_set,
            timeout,
        )

    return moves


def _compute_original_3_line_hashes(
    changes: list[DetailedLineRangeMapping],
    hashed_original_lines: list[int],
) -> SetMap[str, _RangeHolder]:
    original_3_line_hashes: SetMap[str, _RangeHolder] = SetMap()

    for change in changes:
        for i in range(
            change.original.start_line, change.original.end_line_exclusive - 2
        ):
            key = _get_3_line_key(hashed_original_lines, i)
            original_3_line_hashes.add(key, _RangeHolder(LineRange(i, i + 3)))

    return original_3_line_hashes


def _get_3_line_key(hashed_lines: list[int], i: int) -> str:
    return f"{hashed_lines[i - 1]}:{hashed_lines[i + 1 - 1]}:{hashed_lines[i + 2 - 1]}"


def _find_possible_mappings(
    changes: list[DetailedLineRangeMapping],
    hashed_modified_lines: list[int],
    original_3_line_hashes: SetMap[str, _RangeHolder],
    timeout: Timeout,
) -> list[_PossibleMapping] | None:
    possible_mappings: list[_PossibleMapping] = []

    for change in changes:
        last_mappings: list[_PossibleMapping] = []
        for i in range(
            change.modified.start_line, change.modified.end_line_exclusive - 2
        ):
            key = _get_3_line_key(hashed_modified_lines, i)
            current_modified_range = LineRange(i, i + 3)

            next_mappings: list[_PossibleMapping] = []

            def visit(holder: _RangeHolder) -> None:
                _extend_mapping_or_add_new(
                    holder,
                    last_mappings,
                    current_modified_range,
                    next_mappings,
                    possible_mappings,
                )

            original_3_line_hashes.for_each(key, visit)
            last_mappings = next_mappings

        if not timeout.is_valid():
            return None

    return possible_mappings


def _extend_mapping_or_add_new(
    holder: _RangeHolder,
    last_mappings: list[_PossibleMapping],
    current_modified_range: LineRange,
    next_mappings: list[_PossibleMapping],
    possible_mappings: list[_PossibleMapping],
) -> None:
    range_ = holder.range
    for last_mapping in last_mappings:
        if (
            last_mapping.original_line_range.end_line_exclusive + 1
            == range_.end_line_exclusive
            and last_mapping.modified_line_range.end_line_exclusive + 1
            == current_modified_range.end_line_exclusive
        ):
            last_mapping.original_line_range = LineRange(
                last_mapping.original_line_range.start_line,
                range_.end_line_exclusive,
            )
            last_mapping.modified_line_range = LineRange(
                last_mapping.modified_line_range.start_line,
                current_modified_range.end_line_exclusive,
            )
            next_mappings.append(last_mapping)
            return

    mapping = _PossibleMapping(
        modified_line_range=current_modified_range,
        original_line_range=range_,
    )
    possible_mappings.append(mapping)
    next_mappings.append(mapping)


def _select_disjoint_mappings(
    possible_mappings: list[_PossibleMapping],
) -> tuple[list[LineRangeMapping], LineRangeSet, LineRangeSet]:
    possible_mappings.sort(
        key=cmp_to_key(
            reverse_order(
                compare_by(lambda m: len(m.modified_line_range), number_comparator)
            )
        )
    )

    moves: list[LineRangeMapping] = []
    modified_set = LineRangeSet([])
    original_set = LineRangeSet([])

    for mapping in possible_mappings:
        diff_orig_to_mod = (
            mapping.modified_line_range.start_line
            - mapping.original_line_range.start_line
        )
        modified_sections = modified_set.subtract_from(mapping.modified_line_range)
        original_translated_sections = original_set.subtract_from(
            mapping.original_line_range
        ).get_with_delta(diff_orig_to_mod)

        modified_intersected_sections = modified_sections.get_intersection(
            original_translated_sections
        )

        for s in modified_intersected_sections.ranges:
            if len(s) < 3:
                continue

            modified_line_range = s
            original_line_range = s.delta(-diff_orig_to_mod)

            moves.append(LineRangeMapping(original_line_range, modified_line_range))

            modified_set.add_range(modified_line_range)
            original_set.add_range(original_line_range)

    return moves, modified_set, original_set


def _extend_move(
    move: LineRangeMapping,
    monotonous_changes: MonotonousList[DetailedLineRangeMapping],
    changes: list[DetailedLineRangeMapping],
    original_lines: list[str],
    modified_lines: list[str],
    original_set: LineRangeSet,
    modified_set: LineRangeSet,
    timeout: Timeout,
) -> LineRangeMapping:
    lines_above, lines_below = _get_extendable_line_counts(
        move, monotonous_changes, changes
    )

    extend_to_top = _count_extendable_lines(
        move.original.start_line - 1,
        move.modified.start_line - 1,
        -1,
        lines_above,
        original_lines,
        modified_lines,
        original_set,
        modified_set,
        timeout,
    )
    if extend_to_top > 0:
        original_set.add_range(
            LineRange(
                move.original.start_line - extend_to_top,
                move.original.start_line,
            )
        )
        modified_set.add_range(
            LineRange(
                move.modified.start_line - extend_to_top,
                move.modified.start_line,
            )
        )

    extend_to_bottom = _count_extendable_lines(
        move.original.end_line_exclusive,
        move.modified.end_line_exclusive,
        1,
        lines_below,
        original_lines,
        modified_lines,
        original_set,
        modified_set,
        timeout,
    )
    if extend_to_bottom > 0:
        original_set.add_range(
            LineRange(
                move.original.end_line_exclusive,
                move.original.end_line_exclusive + extend_to_bottom,
            )
        )
        modified_set.add_range(
            LineRange(
                move.modified.end_line_exclusive,
                move.modified.end_line_exclusive + extend_to_bottom,
            )
        )

    if extend_to_top > 0 or extend_to_bottom > 0:
        return LineRangeMapping(
            LineRange(
                move.original.start_line - extend_to_top,
                move.original.end_line_exclusive + extend_to_bottom,
            ),
            LineRange(
                move.modified.start_line - extend_to_top,
                move.modified.end_line_exclusive + extend_to_bottom,
            ),
        )

    return move


def _get_extendable_line_counts(
    move: LineRangeMapping,
    monotonous_changes: MonotonousList[DetailedLineRangeMapping],
    changes: list[DetailedLineRangeMapping],
) -> tuple[int, int]:
    first_touching_change_orig = monotonous_changes.find_last_monotonous(
        lambda c: c.original.start_line <= move.original.start_line
    )
    first_touching_change_mod = find_last_monotonous(
        changes,
        lambda c: c.modified.start_line <= move.modified.start_line,
    )
    assert first_touching_change_orig is not None
    assert first_touching_change_mod is not None
    lines_above = max(
        move.original.start_line - first_touching_change_orig.original.start_line,
        move.modified.start_line - first_touching_change_mod.modified.start_line,
    )

    last_touching_change_orig = monotonous_changes.find_last_monotonous(
        lambda c: c.original.start_line < move.original.end_line_exclusive
    )
    last_touching_change_mod = find_last_monotonous(
        changes,
        lambda c: c.modified.start_line < move.modified.end_line_exclusive,
    )
    assert last_touching_change_orig is not None
    assert last_touching_change_mod is not None
    lines_below = max(
        last_touching_change_orig.original.end_line_exclusive
        - move.original.end_line_exclusive,
        last_touching_change_mod.modified.end_line_exclusive
        - move.modified.end_line_exclusive,
    )

    return lines_above, lines_below


def _count_extendable_lines(
    orig_start_line: int,
    mod_start_line: int,
    step: int,
    max_lines: int,
    original_lines: list[str],
    modified_lines: list[str],
    original_set: LineRangeSet,
    modified_set: LineRangeSet,
    timeout: Timeout,
) -> int:
    count = 0
    while count < max_lines:
        orig_line = orig_start_line + step * count
        mod_line = mod_start_line + step * count
        if orig_line > len(original_lines) or mod_line > len(modified_lines):
            break

        if modified_set.contains(mod_line) or original_set.contains(orig_line):
            break

        if not _are_lines_similar(
            original_lines[orig_line - 1],
            modified_lines[mod_line - 1],
            timeout,
        ):
            break

        count += 1

    return count


@dataclass
class _RangeHolder:
    range: LineRange

    def __hash__(self) -> int:
        return id(self)


def _are_lines_similar(line1: str, line2: str, timeout: Timeout) -> bool:
    if line1.strip() == line2.strip():
        return True

    if len(line1) > 300 and len(line2) > 300:
        return False

    myers_diffing_algorithm = MyersDiffAlgorithm()
    result = myers_diffing_algorithm.compute(
        LinesSliceCharSequence([line1], Range(1, 1, 1, len(line1)), False),
        LinesSliceCharSequence([line2], Range(1, 1, 1, len(line2)), False),
        timeout,
    )

    common_non_space_char_count = _count_common_non_space_chars(
        line1, SequenceDiff.invert(result.diffs, len(line1))
    )

    longer_line_length = _count_non_ws_chars(
        line1, line1 if len(line1) > len(line2) else line2
    )
    # JS: 0 / 0 is NaN (and NaN > 0.6 is false), it does not raise.
    ratio = (
        common_non_space_char_count / longer_line_length
        if longer_line_length > 0
        else math.nan
    )
    return ratio > 0.6 and longer_line_length > 10


def _count_common_non_space_chars(line1: str, inverted: list[SequenceDiff]) -> int:
    count = 0
    for seq in inverted:
        for idx in range(seq.seq1_range.start, seq.seq1_range.end_exclusive):
            if not is_space(ord(line1[idx])):
                count += 1

    return count


def _count_non_ws_chars(line1: str, s: str) -> int:
    count = 0
    # Upstream iterates line1.length regardless of s; out-of-range reads
    # yield NaN char codes in JS, which count as non-whitespace.
    for i in range(len(line1)):
        if i >= len(s) or not is_space(ord(s[i])):
            count += 1

    return count


def _join_close_consecutive_moves(
    moves: list[LineRangeMapping],
) -> list[LineRangeMapping]:
    if len(moves) == 0:
        return moves

    moves.sort(
        key=cmp_to_key(compare_by(lambda m: m.original.start_line, number_comparator))
    )

    result = [moves[0]]
    for i in range(1, len(moves)):
        last = result[-1]
        current = moves[i]

        original_dist = current.original.start_line - last.original.end_line_exclusive
        modified_dist = current.modified.start_line - last.modified.end_line_exclusive
        current_move_after_last = original_dist >= 0 and modified_dist >= 0

        if current_move_after_last and original_dist + modified_dist <= 2:
            result[-1] = last.join(current)
            continue

        result.append(current)

    return result


def _remove_moves_in_same_diff(
    changes: list[DetailedLineRangeMapping],
    moves: list[LineRangeMapping],
) -> list[LineRangeMapping]:
    changes_monotonous = MonotonousList(changes)

    def keep(m: LineRangeMapping) -> bool:
        diff_before_end_of_move_original = changes_monotonous.find_last_monotonous(
            lambda c: c.original.start_line < m.original.end_line_exclusive
        ) or LineRangeMapping(LineRange(1, 1), LineRange(1, 1))
        diff_before_end_of_move_modified = find_last_monotonous(
            changes,
            lambda c: c.modified.start_line < m.modified.end_line_exclusive,
        )

        return diff_before_end_of_move_original is not diff_before_end_of_move_modified

    return [m for m in moves if keep(m)]

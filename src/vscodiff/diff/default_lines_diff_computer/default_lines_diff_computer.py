from __future__ import annotations

import math

from vscodiff.common.line_range import LineRange
from vscodiff.common.lists import equals
from vscodiff.common.offset_range import OffsetRange
from vscodiff.common.position import Position
from vscodiff.common.range import Range
from vscodiff.common.text_edit import ListText

from vscodiff.diff.lines_diff_computer import (
    LinesDiff,
    LinesDiffComputer,
    LinesDiffComputerOptions,
    MovedText,
)
from vscodiff.diff.range_mapping import (
    DetailedLineRangeMapping,
    LineRangeMapping,
    RangeMapping,
    line_range_mapping_from_range_mappings,
)
from vscodiff.diff.default_lines_diff_computer.algorithms.diff_algorithm import (
    DateTimeout,
    InfiniteTimeout,
    SequenceDiff,
)
from vscodiff.diff.default_lines_diff_computer.algorithms.dynamic_programming_diffing import (
    DynamicProgrammingDiffing,
)
from vscodiff.diff.default_lines_diff_computer.algorithms.myers_diff_algorithm import (
    MyersDiffAlgorithm,
)
from vscodiff.diff.default_lines_diff_computer.compute_moved_lines import (
    compute_moved_lines,
)
from vscodiff.diff.default_lines_diff_computer.heuristic_sequence_optimizations import (
    extend_diffs_to_entire_word_if_appropriate,
    optimize_sequence_diffs,
    remove_short_matches,
    remove_very_short_matching_lines_between_diffs,
    remove_very_short_matching_text_between_long_diffs,
)
from vscodiff.diff.default_lines_diff_computer.line_sequence import LineSequence
from vscodiff.diff.default_lines_diff_computer.lines_slice_char_sequence import (
    LinesSliceCharSequence,
)


class DefaultLineDiffComputer(LinesDiffComputer):
    def __init__(self):
        self._dynamic_programming_diffing = DynamicProgrammingDiffing()
        self._myers_diffing_algorithm = MyersDiffAlgorithm()

    def compute_diff(
        self,
        original_lines: list[str],
        modified_lines: list[str],
        options: LinesDiffComputerOptions,
    ) -> LinesDiff:
        # Edge case: identical small files — return empty diff
        if len(original_lines) <= 1 and equals(
            original_lines, modified_lines, lambda a, b: a == b
        ):
            return LinesDiff([], [], False)

        # Edge case: one side is a single empty line, the other is not
        if (len(original_lines) == 1 and len(original_lines[0]) == 0) or (
            len(modified_lines) == 1 and len(modified_lines[0]) == 0
        ):
            return LinesDiff(
                [
                    DetailedLineRangeMapping(
                        LineRange(1, len(original_lines) + 1),
                        LineRange(1, len(modified_lines) + 1),
                        [
                            RangeMapping(
                                Range(
                                    1,
                                    1,
                                    len(original_lines),
                                    len(original_lines[-1]) + 1,
                                ),
                                Range(
                                    1,
                                    1,
                                    len(modified_lines),
                                    len(modified_lines[-1]) + 1,
                                ),
                            )
                        ],
                    )
                ],
                [],
                False,
            )

        timeout = (
            InfiniteTimeout.instance
            if options.max_computation_time_ms == 0
            else DateTimeout(options.max_computation_time_ms)
        )
        consider_whitespace_changes = not options.ignore_trim_whitespace

        # Create perfect hashes for trimmed line content
        perfect_hashes: dict[str, int] = {}

        def get_or_create_hash(text: str) -> int:
            if text not in perfect_hashes:
                perfect_hashes[text] = len(perfect_hashes)
            return perfect_hashes[text]

        original_lines_hashes = [
            get_or_create_hash(line.strip()) for line in original_lines
        ]
        modified_lines_hashes = [
            get_or_create_hash(line.strip()) for line in modified_lines
        ]

        sequence1 = LineSequence(original_lines_hashes, original_lines)
        sequence2 = LineSequence(modified_lines_hashes, modified_lines)

        # Choose diff algorithm based on input size
        if sequence1.length + sequence2.length < 1700:
            line_alignment_result = self._dynamic_programming_diffing.compute(
                sequence1,
                sequence2,
                timeout,
                lambda offset1, offset2: (
                    (
                        0.1
                        if len(modified_lines[offset2]) == 0
                        else 1 + math.log(1 + len(modified_lines[offset2]))
                    )
                    if original_lines[offset1] == modified_lines[offset2]
                    else 0.99
                ),
            )
        else:
            line_alignment_result = self._myers_diffing_algorithm.compute(
                sequence1,
                sequence2,
                timeout,
            )

        line_alignments = line_alignment_result.diffs
        hit_timeout = line_alignment_result.hit_timeout
        line_alignments = optimize_sequence_diffs(sequence1, sequence2, line_alignments)
        line_alignments = remove_very_short_matching_lines_between_diffs(
            sequence1, sequence2, line_alignments
        )

        alignments: list[RangeMapping] = []

        seq1_last_start = 0
        seq2_last_start = 0

        def scan_for_whitespace_changes(equal_lines_count: int):
            nonlocal hit_timeout, seq1_last_start, seq2_last_start
            if not consider_whitespace_changes:
                return

            for i in range(equal_lines_count):
                seq1_offset = seq1_last_start + i
                seq2_offset = seq2_last_start + i
                if original_lines[seq1_offset] != modified_lines[seq2_offset]:
                    # This is because of whitespace changes — diff these lines
                    character_diffs = self._refine_diff(
                        original_lines,
                        modified_lines,
                        SequenceDiff(
                            OffsetRange(seq1_offset, seq1_offset + 1),
                            OffsetRange(seq2_offset, seq2_offset + 1),
                        ),
                        timeout,
                        consider_whitespace_changes,
                        options,
                    )
                    for a in character_diffs["mappings"]:
                        alignments.append(a)
                    if character_diffs["hit_timeout"]:
                        hit_timeout = True

        for diff in line_alignments:
            assert (
                diff.seq1_range.start - seq1_last_start
                == diff.seq2_range.start - seq2_last_start
            )

            equal_lines_count = diff.seq1_range.start - seq1_last_start

            scan_for_whitespace_changes(equal_lines_count)

            seq1_last_start = diff.seq1_range.end_exclusive
            seq2_last_start = diff.seq2_range.end_exclusive

            character_diffs = self._refine_diff(
                original_lines,
                modified_lines,
                diff,
                timeout,
                consider_whitespace_changes,
                options,
            )
            if character_diffs["hit_timeout"]:
                hit_timeout = True
            for a in character_diffs["mappings"]:
                alignments.append(a)

        scan_for_whitespace_changes(len(original_lines) - seq1_last_start)

        changes = line_range_mapping_from_range_mappings(
            alignments,
            ListText(original_lines),
            ListText(modified_lines),
        )

        moves: list[MovedText] = []
        if options.compute_moves:
            moves = self._compute_moves(
                changes,
                original_lines,
                modified_lines,
                original_lines_hashes,
                modified_lines_hashes,
                timeout,
                consider_whitespace_changes,
                options,
            )

        # Validate all ranges
        assert self._validate_changes(changes, original_lines, modified_lines)

        return LinesDiff(changes, moves, hit_timeout)

    @staticmethod
    def _validate_changes(
        changes: list[DetailedLineRangeMapping],
        original_lines: list[str],
        modified_lines: list[str],
    ) -> bool:
        for c in changes:
            if c.inner_changes is None:
                return False
            for ic in c.inner_changes:
                valid = (
                    DefaultLineDiffComputer._validate_position(
                        ic.modified_range.get_start_position(), modified_lines
                    )
                    and DefaultLineDiffComputer._validate_position(
                        ic.modified_range.get_end_position(), modified_lines
                    )
                    and DefaultLineDiffComputer._validate_position(
                        ic.original_range.get_start_position(), original_lines
                    )
                    and DefaultLineDiffComputer._validate_position(
                        ic.original_range.get_end_position(), original_lines
                    )
                )
                if not valid:
                    return False
            if not (
                DefaultLineDiffComputer._validate_line_range(c.modified, modified_lines)
                and DefaultLineDiffComputer._validate_line_range(
                    c.original, original_lines
                )
            ):
                return False
        return True

    @staticmethod
    def _validate_position(pos: Position, lines: list[str]) -> bool:
        if pos.line < 1 or pos.line > len(lines):
            return False
        line = lines[pos.line - 1]
        if pos.column < 1 or pos.column > len(line) + 1:
            return False
        return True

    @staticmethod
    def _validate_line_range(range_: LineRange, lines: list[str]) -> bool:
        if range_.start_line < 1 or range_.start_line > len(lines) + 1:
            return False
        if range_.end_line_exclusive < 1 or range_.end_line_exclusive > len(lines) + 1:
            return False
        return True

    def _compute_moves(
        self,
        changes: list[DetailedLineRangeMapping],
        original_lines: list[str],
        modified_lines: list[str],
        hashed_original_lines: list[int],
        hashed_modified_lines: list[int],
        timeout,
        consider_whitespace_changes: bool,
        options: LinesDiffComputerOptions,
    ) -> list[MovedText]:
        moves = compute_moved_lines(
            changes,
            original_lines,
            modified_lines,
            hashed_original_lines,
            hashed_modified_lines,
            timeout,
        )

        moves_with_diffs: list[MovedText] = []
        for m in moves:
            move_changes_result = self._refine_diff(
                original_lines,
                modified_lines,
                SequenceDiff(
                    m.original.to_offset_range(),
                    m.modified.to_offset_range(),
                ),
                timeout,
                consider_whitespace_changes,
                options,
            )
            mappings = line_range_mapping_from_range_mappings(
                move_changes_result["mappings"],
                ListText(original_lines),
                ListText(modified_lines),
                True,
            )
            moves_with_diffs.append(MovedText(m, mappings))

        return moves_with_diffs

    def _refine_diff(
        self,
        original_lines: list[str],
        modified_lines: list[str],
        diff: SequenceDiff,
        timeout,
        consider_whitespace_changes: bool,
        options: LinesDiffComputerOptions,
    ):
        line_range_mapping = _to_line_range_mapping(diff)
        range_mapping = line_range_mapping.to_range_mapping(
            original_lines, modified_lines
        )

        slice1 = LinesSliceCharSequence(
            original_lines,
            range_mapping.original_range,
            consider_whitespace_changes,
        )
        slice2 = LinesSliceCharSequence(
            modified_lines,
            range_mapping.modified_range,
            consider_whitespace_changes,
        )

        if slice1.length + slice2.length < 500:
            diff_result = self._dynamic_programming_diffing.compute(
                slice1, slice2, timeout
            )
        else:
            diff_result = self._myers_diffing_algorithm.compute(slice1, slice2, timeout)

        diffs = diff_result.diffs
        diffs = optimize_sequence_diffs(slice1, slice2, diffs)
        diffs = extend_diffs_to_entire_word_if_appropriate(
            slice1,
            slice2,
            diffs,
            lambda seq, idx: seq.find_word_containing(idx),
        )

        if options.extend_to_subwords:
            diffs = extend_diffs_to_entire_word_if_appropriate(
                slice1,
                slice2,
                diffs,
                lambda seq, idx: seq.find_sub_word_containing(idx),
                True,
            )

        diffs = remove_short_matches(slice1, slice2, diffs)
        diffs = remove_very_short_matching_text_between_long_diffs(
            slice1, slice2, diffs
        )

        result = [
            RangeMapping(
                slice1.translate_range(d.seq1_range),
                slice2.translate_range(d.seq2_range),
            )
            for d in diffs
        ]

        return {
            "mappings": result,
            "hit_timeout": diff_result.hit_timeout,
        }


def _to_line_range_mapping(sequence_diff: SequenceDiff) -> LineRangeMapping:
    return LineRangeMapping(
        LineRange(
            sequence_diff.seq1_range.start + 1,
            sequence_diff.seq1_range.end_exclusive + 1,
        ),
        LineRange(
            sequence_diff.seq2_range.start + 1,
            sequence_diff.seq2_range.end_exclusive + 1,
        ),
    )

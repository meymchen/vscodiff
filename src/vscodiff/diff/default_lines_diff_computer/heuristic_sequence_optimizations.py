from __future__ import annotations

import math
import re
from typing import Callable

from vscodiff.common.lists import for_each_with_neighbors
from vscodiff.common.offset_range import OffsetRange
from vscodiff.diff.default_lines_diff_computer.algorithms.diff_algorithm import (
    OffsetPair,
    Sequence,
    SequenceDiff,
)
from vscodiff.diff.default_lines_diff_computer.line_sequence import LineSequence
from vscodiff.diff.default_lines_diff_computer.lines_slice_char_sequence import (
    LinesSliceCharSequence,
)


def optimize_sequence_diffs(
    sequence1: Sequence,
    sequence2: Sequence,
    sequence_diffs: list[SequenceDiff],
) -> list[SequenceDiff]:
    result = sequence_diffs
    result = _join_sequence_diffs_by_shifting(sequence1, sequence2, result)
    result = _join_sequence_diffs_by_shifting(sequence1, sequence2, result)
    result = _shift_sequence_diffs(sequence1, sequence2, result)
    return result


def _join_sequence_diffs_by_shifting(
    sequence1: Sequence,
    sequence2: Sequence,
    sequence_diffs: list[SequenceDiff],
) -> list[SequenceDiff]:
    if len(sequence_diffs) == 0:
        return sequence_diffs

    result: list[SequenceDiff] = []
    result.append(sequence_diffs[0])

    for i in range(1, len(sequence_diffs)):
        prev_result = result[-1]
        cur = sequence_diffs[i]

        if cur.seq1_range.is_empty or cur.seq2_range.is_empty:
            length = cur.seq1_range.start - prev_result.seq1_range.end_exclusive
            d = 1
            while d <= length:
                if sequence1.get_element(
                    cur.seq1_range.start - d
                ) != sequence1.get_element(
                    cur.seq1_range.end_exclusive - d
                ) or sequence2.get_element(
                    cur.seq2_range.start - d
                ) != sequence2.get_element(cur.seq2_range.end_exclusive - d):
                    break

                d += 1

            d -= 1

            if d == length:
                result[-1] = SequenceDiff(
                    OffsetRange(
                        prev_result.seq1_range.start,
                        cur.seq1_range.end_exclusive - length,
                    ),
                    OffsetRange(
                        prev_result.seq2_range.start,
                        cur.seq2_range.end_exclusive - length,
                    ),
                )
                continue

            cur = cur.delta(-d)

        result.append(cur)

    result2: list[SequenceDiff] = []
    for i in range(len(result) - 1):
        next_result = result[i + 1]
        cur = result[i]

        if cur.seq1_range.is_empty or cur.seq2_range.is_empty:
            length = next_result.seq1_range.start - cur.seq1_range.end_exclusive
            d = 0
            while d < length:
                if not sequence1.is_strongly_equal(
                    cur.seq1_range.start + d, cur.seq1_range.end_exclusive + d
                ) or not sequence2.is_strongly_equal(
                    cur.seq2_range.start + d, cur.seq2_range.end_exclusive + d
                ):
                    break

                d += 1

            if d == length:
                result[i + 1] = SequenceDiff(
                    OffsetRange(
                        cur.seq1_range.start + length,
                        next_result.seq1_range.end_exclusive,
                    ),
                    OffsetRange(
                        cur.seq2_range.start + length,
                        next_result.seq2_range.end_exclusive,
                    ),
                )
                continue

            if d > 0:
                cur = cur.delta(d)

        result2.append(cur)

    if len(result) > 0:
        result2.append(result[-1])

    return result2


def _shift_sequence_diffs(
    sequence1: Sequence,
    sequence2: Sequence,
    sequence_diffs: list[SequenceDiff],
) -> list[SequenceDiff]:
    for i in range(len(sequence_diffs)):
        prev_diff = sequence_diffs[i - 1] if i > 0 else None
        diff = sequence_diffs[i]
        next_diff = sequence_diffs[i + 1] if i + 1 < len(sequence_diffs) else None

        seq1_valid_range = OffsetRange(
            prev_diff.seq1_range.end_exclusive + 1 if prev_diff else 0,
            next_diff.seq1_range.start - 1 if next_diff else sequence1.length,
        )
        seq2_valid_range = OffsetRange(
            prev_diff.seq2_range.end_exclusive + 1 if prev_diff else 0,
            next_diff.seq2_range.start - 1 if next_diff else sequence2.length,
        )

        if diff.seq1_range.is_empty:
            sequence_diffs[i] = _shift_diff_to_better_position(
                diff,
                sequence1,
                sequence2,
                seq1_valid_range,
                seq2_valid_range,
            )
        elif diff.seq2_range.is_empty:
            sequence_diffs[i] = _shift_diff_to_better_position(
                diff.swap(),
                sequence2,
                sequence1,
                seq2_valid_range,
                seq1_valid_range,
            ).swap()

    return sequence_diffs


def _shift_diff_to_better_position(
    diff: SequenceDiff,
    sequence1: Sequence,
    sequence2: Sequence,
    seq1_valid_range: OffsetRange,
    seq2_valid_range: OffsetRange,
) -> SequenceDiff:
    max_shift_limit = 100

    delta_before = 1
    while (
        diff.seq1_range.start - delta_before >= seq1_valid_range.start
        and diff.seq2_range.start - delta_before >= seq2_valid_range.start
        and sequence2.is_strongly_equal(
            diff.seq2_range.start - delta_before,
            diff.seq2_range.end_exclusive - delta_before,
        )
        and delta_before < max_shift_limit
    ):
        delta_before += 1

    delta_before -= 1

    delta_after = 0
    while (
        diff.seq1_range.start + delta_after < seq1_valid_range.end_exclusive
        and diff.seq2_range.end_exclusive + delta_after < seq2_valid_range.end_exclusive
        and sequence2.is_strongly_equal(
            diff.seq2_range.start + delta_after,
            diff.seq2_range.end_exclusive + delta_after,
        )
        and delta_after < max_shift_limit
    ):
        delta_after += 1

    if delta_before == 0 and delta_after == 0:
        return diff

    best_delta = 0
    best_score = -1
    for delta in range(-delta_before, delta_after + 1):
        seq2_offset_start = diff.seq2_range.start + delta
        seq2_offset_end_exclusive = diff.seq2_range.end_exclusive + delta
        seq1_offset = diff.seq1_range.start + delta

        score = (
            sequence1.get_boundary_score(seq1_offset)
            + sequence2.get_boundary_score(seq2_offset_start)
            + sequence2.get_boundary_score(seq2_offset_end_exclusive)
        )
        if score > best_score:
            best_score = score
            best_delta = delta

    return diff.delta(best_delta)


def remove_short_matches(
    sequence1: Sequence,
    sequence2: Sequence,
    sequence_diffs: list[SequenceDiff],
) -> list[SequenceDiff]:
    result: list[SequenceDiff] = []
    for s in sequence_diffs:
        last = result[-1] if len(result) > 0 else None
        if not last:
            result.append(s)
            continue

        if (
            s.seq1_range.start - last.seq1_range.end_exclusive <= 2
            or s.seq2_range.start - last.seq2_range.end_exclusive <= 2
        ):
            result[-1] = SequenceDiff(
                last.seq1_range.join(s.seq1_range),
                last.seq2_range.join(s.seq2_range),
            )
        else:
            result.append(s)

    return result


def extend_diffs_to_entire_word_if_appropriate(
    sequence1: LinesSliceCharSequence,
    sequence2: LinesSliceCharSequence,
    sequence_diffs: list[SequenceDiff],
    find_parent: Callable[[LinesSliceCharSequence, int], OffsetRange | None],
    force: bool = False,
) -> list[SequenceDiff]:
    equal_mappings = SequenceDiff.invert(sequence_diffs, sequence1.length)

    additional: list[SequenceDiff] = []

    last_point = OffsetPair(0, 0)

    def scan_word(pair: OffsetPair, equal_mapping: SequenceDiff) -> None:
        nonlocal last_point
        if pair.offset1 < last_point.offset1 or pair.offset2 < last_point.offset2:
            return

        w1 = find_parent(sequence1, pair.offset1)
        w2 = find_parent(sequence2, pair.offset2)
        if not w1 or not w2:
            return

        w = SequenceDiff(w1, w2)
        equal_part = w.intersect(equal_mapping)
        assert equal_part is not None

        equal_chars1 = len(equal_part.seq1_range)
        equal_chars2 = len(equal_part.seq2_range)

        while len(equal_mappings) > 0:
            next_ = equal_mappings[0]
            intersects = next_.seq1_range.intersects(
                w.seq1_range
            ) or next_.seq2_range.intersects(w.seq2_range)
            if not intersects:
                break

            v1 = find_parent(sequence1, next_.seq1_range.start)
            v2 = find_parent(sequence2, next_.seq2_range.start)
            assert v1 is not None and v2 is not None
            v = SequenceDiff(v1, v2)
            equal_part_inner = v.intersect(next_)
            assert equal_part_inner is not None

            equal_chars1 += len(equal_part_inner.seq1_range)
            equal_chars2 += len(equal_part_inner.seq2_range)

            w = w.join(v)

            if w.seq1_range.end_exclusive >= next_.seq1_range.end_exclusive:
                equal_mappings.pop(0)
            else:
                break

        if (
            force
            and equal_chars1 + equal_chars2 < len(w.seq1_range) + len(w.seq2_range)
        ) or equal_chars1 + equal_chars2 < (
            (len(w.seq1_range) + len(w.seq2_range)) * 2
        ) / 3:
            additional.append(w)

        last_point = w.get_end_exclusive()

    while len(equal_mappings) > 0:
        next_ = equal_mappings.pop(0)
        if next_.seq1_range.is_empty:
            continue

        scan_word(next_.get_starts(), next_)
        scan_word(next_.get_end_exclusive().delta(-1), next_)

    merged = _merge_sequence_diffs(sequence_diffs, additional)
    return merged


def _merge_sequence_diffs(
    sequence_diffs1: list[SequenceDiff],
    sequence_diffs2: list[SequenceDiff],
) -> list[SequenceDiff]:
    result: list[SequenceDiff] = []

    while len(sequence_diffs1) > 0 or len(sequence_diffs2) > 0:
        sd1 = sequence_diffs1[0] if len(sequence_diffs1) > 0 else None
        sd2 = sequence_diffs2[0] if len(sequence_diffs2) > 0 else None

        if sd1 and (not sd2 or sd1.seq1_range.start < sd2.seq1_range.start):
            next_ = sequence_diffs1.pop(0)
        else:
            next_ = sequence_diffs2.pop(0)

        if (
            len(result) > 0
            and result[-1].seq1_range.end_exclusive >= next_.seq1_range.start
        ):
            result[-1] = result[-1].join(next_)
        else:
            result.append(next_)

    return result


def remove_very_short_matching_lines_between_diffs(
    sequence1: LineSequence,
    _sequence2: LineSequence,
    sequence_diffs: list[SequenceDiff],
) -> list[SequenceDiff]:
    diffs = sequence_diffs
    if len(diffs) == 0:
        return diffs

    counter = 0
    should_repeat = True
    while should_repeat and counter < 10:
        should_repeat = False

        result: list[SequenceDiff] = [diffs[0]]

        for i in range(1, len(diffs)):
            cur = diffs[i]
            last_result = result[-1]

            def should_join_diffs(
                before: SequenceDiff,
                after: SequenceDiff,
            ) -> bool:
                unchanged_range = OffsetRange(
                    last_result.seq1_range.end_exclusive,
                    cur.seq1_range.start,
                )

                unchanged_text = sequence1.get_text(unchanged_range)
                unchanged_text_without_ws = re.sub(r"\s", "", unchanged_text)
                if len(unchanged_text_without_ws) <= 4 and (
                    len(before.seq1_range) + len(before.seq2_range) > 5
                    or len(after.seq1_range) + len(after.seq2_range) > 5
                ):
                    return True

                return False

            should_join = should_join_diffs(last_result, cur)
            if should_join:
                should_repeat = True
                result[-1] = result[-1].join(cur)
            else:
                result.append(cur)

        diffs = result
        counter += 1

    return diffs


def remove_very_short_matching_text_between_long_diffs(
    sequence1: LinesSliceCharSequence,
    sequence2: LinesSliceCharSequence,
    sequence_diffs: list[SequenceDiff],
) -> list[SequenceDiff]:
    diffs = sequence_diffs
    if len(diffs) == 0:
        return diffs

    counter = 0
    should_repeat = True
    while should_repeat and counter < 10:
        should_repeat = False

        result: list[SequenceDiff] = [diffs[0]]

        for i in range(1, len(diffs)):
            cur = diffs[i]
            last_result = result[-1]

            def should_join_diffs(
                before: SequenceDiff,
                after: SequenceDiff,
            ) -> bool:
                unchanged_range = OffsetRange(
                    last_result.seq1_range.end_exclusive,
                    cur.seq1_range.start,
                )

                unchanged_line_count = sequence1.count_lines_in(unchanged_range)
                if unchanged_line_count > 5 or len(unchanged_range) > 500:
                    return False

                unchanged_text = sequence1.get_text(unchanged_range).strip()
                if (
                    len(unchanged_text) > 20
                    or len(re.split(r"\r\n|\r|\n", unchanged_text)) > 1
                ):
                    return False

                before_line_count1 = sequence1.count_lines_in(before.seq1_range)
                before_seq1_length = len(before.seq1_range)
                before_line_count2 = sequence2.count_lines_in(before.seq2_range)
                before_seq2_length = len(before.seq2_range)

                after_line_count1 = sequence1.count_lines_in(after.seq1_range)
                after_seq1_length = len(after.seq1_range)
                after_line_count2 = sequence2.count_lines_in(after.seq2_range)
                after_seq2_length = len(after.seq2_range)

                max_value = 2 * 40 + 50

                def cap(v: float) -> float:
                    return min(v, max_value)

                if (
                    math.pow(
                        math.pow(cap(before_line_count1 * 40 + before_seq1_length), 1.5)
                        + math.pow(
                            cap(before_line_count2 * 40 + before_seq2_length), 1.5
                        ),
                        1.5,
                    )
                    + math.pow(
                        math.pow(cap(after_line_count1 * 40 + after_seq1_length), 1.5)
                        + math.pow(
                            cap(after_line_count2 * 40 + after_seq2_length), 1.5
                        ),
                        1.5,
                    )
                ) > (max_value**1.5) ** 1.5 * 1.3:
                    return True

                return False

            should_join = should_join_diffs(last_result, cur)
            if should_join:
                should_repeat = True
                result[-1] = result[-1].join(cur)
            else:
                result.append(cur)

        diffs = result
        counter += 1

    new_diffs: list[SequenceDiff] = []

    def visit(
        prev: SequenceDiff | None,
        cur: SequenceDiff,
        next_: SequenceDiff | None,
    ) -> None:
        new_diff = cur

        def should_mark_as_changed(text: str) -> bool:
            return (
                len(text) > 0
                and len(text.strip()) <= 3
                and len(cur.seq1_range) + len(cur.seq2_range) > 100
            )

        full_range1 = sequence1.extend_to_full_lines(cur.seq1_range)
        prefix = sequence1.get_text(
            OffsetRange(full_range1.start, cur.seq1_range.start)
        )
        if should_mark_as_changed(prefix):
            new_diff = new_diff.delta_start(-len(prefix))

        suffix = sequence1.get_text(
            OffsetRange(cur.seq1_range.end_exclusive, full_range1.end_exclusive)
        )
        if should_mark_as_changed(suffix):
            new_diff = new_diff.delta_end(len(suffix))

        available_space = SequenceDiff.from_offset_pairs(
            prev.get_end_exclusive() if prev else OffsetPair.zero(),
            next_.get_starts() if next_ else OffsetPair.max(),
        )
        intersected = new_diff.intersect(available_space)
        if intersected is None:
            return
        if (
            len(new_diffs) > 0
            and intersected.get_starts() == new_diffs[-1].get_end_exclusive()
        ):
            new_diffs[-1] = new_diffs[-1].join(intersected)
        else:
            new_diffs.append(intersected)

    for_each_with_neighbors(diffs, visit)

    return new_diffs

"""Unit tests for LegacyLinesDiffComputer (the top-level wrapper) and
DiffComputer internals (LineSequence, CharSequence, CharChange construction).

Run with: uv run pytest tests/test_legacy_diff.py -v
"""

from __future__ import annotations

from vscodiff.common.diff.diff_change import DiffChange
from vscodiff.common.line_range import LineRange
from vscodiff.diff.legacy_lines_diff_computer import (
    CharChange,
    CharSequence,
    DiffComputer,
    DiffComputerOpts,
    DiffComputerResult,
    LegacyLinesDiffComputer,
    LineSequence,
    _post_process_char_changes,
)
from vscodiff.diff.lines_diff_computer import LinesDiffComputerOptions


# ---------------------------------------------------------------------------
# LineSequence
# ---------------------------------------------------------------------------


class TestLineSequence:
    def test_empty_lines(self) -> None:
        seq = LineSequence([])
        assert seq.get_elements() == []

    def test_single_line(self) -> None:
        seq = LineSequence(["hello"])
        assert seq.get_elements() == ["hello"]
        assert seq.get_start_line_number(0) == 1
        assert seq.get_end_line_number(0) == 1

    def test_trimmed_elements_strip_whitespace(self) -> None:
        """get_elements strips leading/trailing whitespace from each line."""
        seq = LineSequence(["  foo  ", " bar", "baz "])
        assert seq.get_elements() == ["foo", "bar", "baz"]

    def test_start_end_line_number_1_based(self) -> None:
        seq = LineSequence(["a", "b", "c"])
        assert seq.get_start_line_number(0) == 1
        assert seq.get_end_line_number(0) == 1
        assert seq.get_start_line_number(2) == 3
        assert seq.get_end_line_number(2) == 3

    def test_strict_element_returns_raw(self) -> None:
        seq = LineSequence(["  hello "])
        assert seq.get_strict_element(0) == "  hello "

    def test_create_char_sequence_no_ignore_whitespace(self) -> None:
        seq = LineSequence(["ab", "cd"])
        cs = seq.create_char_sequence(False, 0, 1)
        # "ab" + '\n' + "cd" → 5 char codes
        elements = cs.get_elements()
        assert len(elements) == 5  # a, b, \n, c, d

    def test_create_char_sequence_ignore_trim_whitespace(self) -> None:
        seq = LineSequence(["  ab  "])
        cs = seq.create_char_sequence(True, 0, 0)
        # whitespace trimmed: only "ab" remains
        elements = cs.get_elements()
        assert len(elements) == 2
        assert chr(elements[0]) == "a"
        assert chr(elements[1]) == "b"


# ---------------------------------------------------------------------------
# CharSequence
# ---------------------------------------------------------------------------


class TestCharSequence:
    def test_empty(self) -> None:
        cs = CharSequence([], [], [])
        assert cs.get_elements() == []

    def test_single_char(self) -> None:
        cs = CharSequence([ord("X")], [1], [3])
        assert cs.get_elements() == [ord("X")]
        assert cs.get_start_line_number(0) == 1
        assert cs.get_start_column(0) == 3
        assert cs.get_end_column(0) == 4
        assert cs.get_end_line_number(0) == 1

    def test_linefeed_end_line_number(self) -> None:
        cs = CharSequence(
            [ord("a"), 10, ord("b")],  # 10 = \n
            [1, 1, 2],
            [1, 2, 1],
        )
        assert cs.get_end_line_number(0) == 1
        assert cs.get_end_line_number(1) == 2  # linefeed: end line = next line
        assert cs.get_end_line_number(2) == 2

    def test_index_bounds(self) -> None:
        cs = CharSequence([ord("a")], [1], [1])
        import pytest

        # Index equal to length is valid (returns end line of last element)
        # Index strictly greater than length raises IndexError
        with pytest.raises(IndexError):
            cs.get_start_line_number(2)


# ---------------------------------------------------------------------------
# CharChange.create_from_diff_change
# ---------------------------------------------------------------------------


class TestCharChange:
    def test_create_from_diff_change_single_line(self) -> None:
        """Map a single-line DiffChange through a CharSequence."""
        seq = CharSequence(
            [ord("a"), ord("b"), ord("c")],
            [1, 1, 1],
            [1, 2, 3],
        )
        dc = DiffChange(
            original_start=0, original_length=1, modified_start=0, modified_length=1
        )
        cc = CharChange.create_from_diff_change(dc, seq, seq)
        assert cc.original_start_line_number == 1
        assert cc.original_start_column == 1
        assert cc.original_end_line_number == 1
        assert cc.original_end_column == 2
        assert cc.modified_start_line_number == 1
        assert cc.modified_start_column == 1
        assert cc.modified_end_line_number == 1
        assert cc.modified_end_column == 2

    def test_create_from_diff_change_multi_line(self) -> None:
        """CharChange spanning across line boundaries."""
        # Original: "a\nb" → char codes [97, 10, 98], lines [1,1,2], cols [1,2,1]
        seq_orig = CharSequence(
            [ord("a"), 10, ord("b")],
            [1, 1, 2],
            [1, 2, 1],
        )
        # Modified: "a\nx" → char codes [97, 10, 120], lines [1,1,2], cols [1,2,1]
        seq_mod = CharSequence(
            [ord("a"), 10, ord("x")],
            [1, 1, 2],
            [1, 2, 1],
        )
        dc = DiffChange(
            original_start=2, original_length=1, modified_start=2, modified_length=1
        )
        cc = CharChange.create_from_diff_change(dc, seq_orig, seq_mod)
        assert cc.original_start_line_number == 2
        assert cc.original_start_column == 1
        assert cc.original_end_line_number == 2
        assert cc.original_end_column == 2
        assert cc.modified_start_line_number == 2
        assert cc.modified_start_column == 1
        assert cc.modified_end_line_number == 2
        assert cc.modified_end_column == 2


# ---------------------------------------------------------------------------
# _post_process_char_changes
# ---------------------------------------------------------------------------


class TestPostProcessCharChanges:
    def test_empty(self) -> None:
        assert _post_process_char_changes([]) == []

    def test_single_change(self) -> None:
        dc = DiffChange(0, 1, 0, 1)
        assert _post_process_char_changes([dc]) == [dc]

    def test_no_merge_when_large_gap(self) -> None:
        """When matching_length >= 3, changes should NOT be merged."""
        # Change 1: [0,2) in original, [0,2) in modified
        c1 = DiffChange(0, 2, 0, 2)
        # Matching region: original [2,5), modified [2,5) → length 3
        # Change 2: [5,6) in original, [5,6) in modified
        c2 = DiffChange(5, 1, 5, 1)
        result = _post_process_char_changes([c1, c2])
        assert len(result) == 2
        assert result[0] == c1
        assert result[1] == c2

    def test_merge_when_small_gap(self) -> None:
        """When matching_length < 3, changes SHOULD be merged."""
        # Change 1: [0,1) in original, [0,1) in modified
        c1 = DiffChange(0, 1, 0, 1)
        # Matching region: original [1,2), modified [1,2) → length 1 (< 3)
        # Change 2: [2,1) in original, [2,1) in modified
        c2 = DiffChange(2, 1, 2, 1)
        result = _post_process_char_changes([c1, c2])
        assert len(result) == 1
        assert result[0].original_start == 0
        assert result[0].original_length == 3
        assert result[0].modified_start == 0
        assert result[0].modified_length == 3


# ---------------------------------------------------------------------------
# DiffComputer special cases
# ---------------------------------------------------------------------------


class TestDiffComputerSpecials:
    def test_both_empty_single_line(self) -> None:
        """Both original and modified are [''] (single empty line)."""
        dc = DiffComputer(
            [""],
            [""],
            DiffComputerOpts(
                should_compute_char_changes=True,
                should_post_process_char_changes=False,
                should_ignore_trim_whitespace=False,
                should_make_pretty_diff=True,
                max_computation_time=0,
            ),
        )
        result = dc.compute_diff()
        assert result.changes == []
        assert result.quit_early is False

    def test_empty_original_to_content(self) -> None:
        """Original is empty string, modified has content."""
        dc = DiffComputer(
            [""],
            ["hello"],
            DiffComputerOpts(
                True,
                False,
                False,
                True,
                0,
            ),
        )
        result = dc.compute_diff()
        assert len(result.changes) == 1
        c = result.changes[0]
        assert c.original_start_line_number == 1
        assert c.original_end_line_number == 1
        assert c.modified_start_line_number == 1
        assert c.modified_end_line_number == 1

    def test_content_to_empty_modified(self) -> None:
        """Original has content, modified is empty string."""
        dc = DiffComputer(
            ["hello"],
            [""],
            DiffComputerOpts(
                True,
                False,
                False,
                True,
                0,
            ),
        )
        result = dc.compute_diff()
        assert len(result.changes) == 1
        c = result.changes[0]
        assert c.original_start_line_number == 1
        assert c.original_end_line_number == 1
        assert c.modified_start_line_number == 1
        assert c.modified_end_line_number == 1

    def test_identical_multiline(self) -> None:
        dc = DiffComputer(
            ["a", "b", "c"],
            ["a", "b", "c"],
            DiffComputerOpts(
                True,
                False,
                False,
                True,
                0,
            ),
        )
        result = dc.compute_diff()
        assert result.changes == []
        assert result.quit_early is False

    def test_computation_time_limit_respected(self) -> None:
        """max_computation_time=0 means no time limit."""
        dc = DiffComputer(
            ["line" for _ in range(100)],
            ["line" for _ in range(100)],
            DiffComputerOpts(True, False, False, True, 0),
        )
        result = dc.compute_diff()
        assert result.changes == []


# ---------------------------------------------------------------------------
# LegacyLinesDiffComputer (top-level wrapper)
# ---------------------------------------------------------------------------


class TestLegacyLinesDiffComputer:
    def test_simple_line_insertion(self) -> None:
        """Verify the LegacyLinesDiffComputer wrapper works end-to-end."""
        computer = LegacyLinesDiffComputer()
        result = computer.compute_diff(
            ["line"],
            ["line", "new line"],
            LinesDiffComputerOptions(
                ignore_trim_whitespace=False,
                max_computation_time_ms=0,
                compute_moves=False,
                extend_to_subwords=False,
            ),
        )
        assert len(result.changes) == 1
        assert result.hit_timeout is False

    def test_simple_line_deletion(self) -> None:
        computer = LegacyLinesDiffComputer()
        result = computer.compute_diff(
            ["line", "extra"],
            ["line"],
            LinesDiffComputerOptions(
                ignore_trim_whitespace=False,
                max_computation_time_ms=0,
                compute_moves=False,
                extend_to_subwords=False,
            ),
        )
        assert len(result.changes) == 1
        assert result.hit_timeout is False

    def test_identical_text(self) -> None:
        computer = LegacyLinesDiffComputer()
        result = computer.compute_diff(
            ["a", "b", "c"],
            ["a", "b", "c"],
            LinesDiffComputerOptions(
                ignore_trim_whitespace=False,
                max_computation_time_ms=0,
                compute_moves=False,
                extend_to_subwords=False,
            ),
        )
        assert len(result.changes) == 0
        assert result.hit_timeout is False

    def test_compute_diff_returns_lines_diff(self) -> None:
        """Ensure the return type has the expected attributes."""
        from vscodiff.diff.lines_diff_computer import LinesDiff

        computer = LegacyLinesDiffComputer()
        result = computer.compute_diff(
            ["a"],
            ["b"],
            LinesDiffComputerOptions(False, 0, False, False),
        )
        assert isinstance(result, LinesDiff)
        assert hasattr(result, "changes")
        assert hasattr(result, "moves")
        assert hasattr(result, "hit_timeout")

    def test_line_range_mapping(self) -> None:
        """Verify that changes are properly mapped to DetailedLineRangeMapping."""
        computer = LegacyLinesDiffComputer()
        result = computer.compute_diff(
            ["a", "b", "c", "d"],
            ["a", "x", "c", "d"],
            LinesDiffComputerOptions(False, 0, False, False),
        )
        assert len(result.changes) == 1
        change = result.changes[0]
        # Should be a DetailedLineRangeMapping with original and modified ranges
        assert isinstance(change.original, LineRange)
        assert isinstance(change.modified, LineRange)


# ---------------------------------------------------------------------------
# DiffComputerResult and DiffComputerOpts dataclasses
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_diff_computer_result(self) -> None:
        r = DiffComputerResult(quit_early=False, changes=[])
        assert r.quit_early is False
        assert r.changes == []

    def test_diff_computer_opts(self) -> None:
        opts = DiffComputerOpts(True, True, False, True, 5000)
        assert opts.should_compute_char_changes is True
        assert opts.should_post_process_char_changes is True
        assert opts.should_ignore_trim_whitespace is False
        assert opts.should_make_pretty_diff is True
        assert opts.max_computation_time == 5000

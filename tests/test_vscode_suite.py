"""Port of Microsoft VS Code's official DiffComputer test suite.

Tests the legacy LCS-based line diff algorithm (DiffComputer/LegacyLinesDiffComputer)
against VS Code's expected behavior.  Line numbers are 1‑based, matching the
original TypeScript output format.

Run with: uv run pytest tests/test_vscode_suite.py -v
"""

from __future__ import annotations

from vscodiff.diff.legacy_lines_diff_computer import (
    CharChange,
    DiffComputer,
    DiffComputerOpts,
    LineChange,
)


# ---------------------------------------------------------------------------
# Helper factories -- mirror the TypeScript helper functions exactly
# ---------------------------------------------------------------------------


def _create_line_deletion(
    start_line: int, end_line: int, modified_line: int
) -> LineChange:
    """Create a LineChange representing deleted lines."""
    return LineChange(
        original_start_line_number=start_line,
        original_end_line_number=end_line,
        modified_start_line_number=modified_line,
        modified_end_line_number=0,
        char_changes=None,
    )


def _create_line_insertion(
    start_line: int, end_line: int, original_line: int
) -> LineChange:
    """Create a LineChange representing inserted lines."""
    return LineChange(
        original_start_line_number=original_line,
        original_end_line_number=0,
        modified_start_line_number=start_line,
        modified_end_line_number=end_line,
        char_changes=None,
    )


def _create_line_change(
    original_start: int,
    original_end: int,
    modified_start: int,
    modified_end: int,
    char_changes: list[CharChange] | None = None,
) -> LineChange:
    """Create a LineChange representing changed lines with optional char‑level changes."""
    return LineChange(
        original_start_line_number=original_start,
        original_end_line_number=original_end,
        modified_start_line_number=modified_start,
        modified_end_line_number=modified_end,
        char_changes=char_changes,
    )


def _create_char_change(
    osl: int,
    osc: int,
    oel: int,
    oec: int,
    msl: int,
    msc: int,
    mel: int,
    mec: int,
) -> CharChange:
    """Create a CharChange with explicit original and modified ranges."""
    return CharChange(
        original_start_line_number=osl,
        original_start_column=osc,
        original_end_line_number=oel,
        original_end_column=oec,
        modified_start_line_number=msl,
        modified_start_column=msc,
        modified_end_line_number=mel,
        modified_end_column=mec,
    )


# ---------------------------------------------------------------------------
# Assertion helper
# ---------------------------------------------------------------------------


def _do_assert_diff(
    original_lines: list[str],
    modified_lines: list[str],
    expected_changes: list[LineChange],
    *,
    should_compute_char_changes: bool = True,
    should_post_process_char_changes: bool = False,
    should_ignore_trim_whitespace: bool = False,
) -> None:
    """Run diff and compare the produced LineChange list against expected."""
    diff_computer = DiffComputer(
        original_lines,
        modified_lines,
        DiffComputerOpts(
            should_compute_char_changes=should_compute_char_changes,
            should_post_process_char_changes=should_post_process_char_changes,
            should_ignore_trim_whitespace=should_ignore_trim_whitespace,
            should_make_pretty_diff=True,
            max_computation_time=0,
        ),
    )
    result = diff_computer.compute_diff()
    actual = result.changes

    assert len(actual) == len(expected_changes), (
        f"Change count mismatch: expected {len(expected_changes)}, got {len(actual)}\n"
        f"  actual:   {actual}\n"
        f"  expected: {expected_changes}"
    )

    for i, (a, e) in enumerate(zip(actual, expected_changes)):
        assert a == e, f"Change [{i}] mismatch:\n  actual:   {a}\n  expected: {e}"


# ===========================================================================
# Test class -- all 40+ tests from VS Code's DiffComputer test suite
# ===========================================================================


class TestVSCodeDiffComputer:
    """Port of 'Editor Diff - DiffComputer' from VS Code's test suite."""

    # -- Insertions ----------------------------------------------------------

    def test_one_inserted_line_below(self) -> None:
        """Single line inserted after the only existing line."""
        _do_assert_diff(
            ["line"],
            ["line", "new line"],
            [_create_line_insertion(2, 2, 1)],
        )

    def test_two_inserted_lines_below(self) -> None:
        """Two lines inserted after the only existing line."""
        _do_assert_diff(
            ["line"],
            ["line", "new line", "another new line"],
            [_create_line_insertion(2, 3, 1)],
        )

    def test_one_inserted_line_above(self) -> None:
        """Single line inserted before the only existing line."""
        _do_assert_diff(
            ["line"],
            ["new line", "line"],
            [_create_line_insertion(1, 1, 0)],
        )

    def test_two_inserted_lines_above(self) -> None:
        """Two lines inserted before the only existing line."""
        _do_assert_diff(
            ["line"],
            ["new line", "another new line", "line"],
            [_create_line_insertion(1, 2, 0)],
        )

    def test_one_inserted_line_in_middle(self) -> None:
        """One line inserted between existing lines."""
        _do_assert_diff(
            ["line1", "line2", "line3", "line4"],
            ["line1", "line2", "new line", "line3", "line4"],
            [_create_line_insertion(3, 3, 2)],
        )

    def test_two_inserted_lines_in_middle(self) -> None:
        """Two consecutive lines inserted between existing lines."""
        _do_assert_diff(
            ["line1", "line2", "line3", "line4"],
            ["line1", "line2", "new line", "another new line", "line3", "line4"],
            [_create_line_insertion(3, 4, 2)],
        )

    def test_two_inserted_lines_in_middle_interrupted(self) -> None:
        """Two insertions separated by an unchanged line."""
        _do_assert_diff(
            ["line1", "line2", "line3", "line4"],
            ["line1", "line2", "new line", "line3", "another new line", "line4"],
            [
                _create_line_insertion(3, 3, 2),
                _create_line_insertion(5, 5, 3),
            ],
        )

    # -- Deletions -----------------------------------------------------------

    def test_one_deleted_line_below(self) -> None:
        """One line deleted from after the matched line."""
        _do_assert_diff(
            ["line", "new line"],
            ["line"],
            [_create_line_deletion(2, 2, 1)],
        )

    def test_two_deleted_lines_below(self) -> None:
        """Two lines deleted from after the matched line."""
        _do_assert_diff(
            ["line", "new line", "another new line"],
            ["line"],
            [_create_line_deletion(2, 3, 1)],
        )

    def test_one_deleted_line_above(self) -> None:
        """One line deleted from before the matched line."""
        _do_assert_diff(
            ["new line", "line"],
            ["line"],
            [_create_line_deletion(1, 1, 0)],
        )

    def test_two_deleted_lines_above(self) -> None:
        """Two lines deleted from before the matched line."""
        _do_assert_diff(
            ["new line", "another new line", "line"],
            ["line"],
            [_create_line_deletion(1, 2, 0)],
        )

    def test_one_deleted_line_in_middle(self) -> None:
        """One line deleted from between existing lines."""
        _do_assert_diff(
            ["line1", "line2", "new line", "line3", "line4"],
            ["line1", "line2", "line3", "line4"],
            [_create_line_deletion(3, 3, 2)],
        )

    def test_two_deleted_lines_in_middle(self) -> None:
        """Two consecutive lines deleted from between existing lines."""
        _do_assert_diff(
            ["line1", "line2", "new line", "another new line", "line3", "line4"],
            ["line1", "line2", "line3", "line4"],
            [_create_line_deletion(3, 4, 2)],
        )

    def test_two_deleted_lines_in_middle_interrupted(self) -> None:
        """Two deletions in the middle, separated by an unchanged line."""
        _do_assert_diff(
            [
                "line1",
                "line2",
                "new line",
                "line3",
                "another new line",
                "line4",
            ],
            ["line1", "line2", "line3", "line4"],
            [
                _create_line_deletion(3, 3, 2),
                _create_line_deletion(5, 5, 3),
            ],
        )

    # -- Char‑level changes --------------------------------------------------

    def test_one_line_changed_chars_inserted_at_end(self) -> None:
        """Characters appended to the end of a line."""
        _do_assert_diff(
            ["line"],
            ["line changed"],
            [
                _create_line_change(
                    1,
                    1,
                    1,
                    1,
                    [_create_char_change(1, 5, 1, 5, 1, 5, 1, 13)],
                )
            ],
        )

    def test_one_line_changed_chars_inserted_at_beginning(self) -> None:
        """Characters prepended to a line."""
        _do_assert_diff(
            ["line"],
            ["my line"],
            [
                _create_line_change(
                    1,
                    1,
                    1,
                    1,
                    [_create_char_change(1, 1, 1, 1, 1, 1, 1, 4)],
                )
            ],
        )

    def test_one_line_changed_chars_inserted_in_middle(self) -> None:
        """Characters inserted in the middle of a line."""
        _do_assert_diff(
            ["abba"],
            ["abzzba"],
            [
                _create_line_change(
                    1,
                    1,
                    1,
                    1,
                    [_create_char_change(1, 3, 1, 3, 1, 3, 1, 5)],
                )
            ],
        )

    def test_one_line_changed_chars_inserted_in_middle_two_spots(self) -> None:
        """Characters inserted at two separate spots in the same line."""
        _do_assert_diff(
            ["abba"],
            ["abzzbzza"],
            [
                _create_line_change(
                    1,
                    1,
                    1,
                    1,
                    [
                        _create_char_change(1, 3, 1, 3, 1, 3, 1, 5),
                        _create_char_change(1, 4, 1, 4, 1, 6, 1, 8),
                    ],
                )
            ],
        )

    def test_one_line_changed_chars_deleted_1(self) -> None:
        """Consecutive characters deleted from the middle of a line."""
        _do_assert_diff(
            ["abcdefg"],
            ["abcfg"],
            [
                _create_line_change(
                    1,
                    1,
                    1,
                    1,
                    [_create_char_change(1, 4, 1, 6, 1, 4, 1, 4)],
                )
            ],
        )

    def test_one_line_changed_chars_deleted_2(self) -> None:
        """Two separate character deletions in the same line."""
        _do_assert_diff(
            ["abcdefg"],
            ["acfg"],
            [
                _create_line_change(
                    1,
                    1,
                    1,
                    1,
                    [
                        _create_char_change(1, 2, 1, 3, 1, 2, 1, 2),
                        _create_char_change(1, 4, 1, 6, 1, 3, 1, 3),
                    ],
                )
            ],
        )

    # -- Multi‑line changes --------------------------------------------------

    def test_two_lines_changed_1(self) -> None:
        """Two lines collapsed into one with a shared trailing change."""
        _do_assert_diff(
            ["abcd", "efgh"],
            ["abcz"],
            [
                _create_line_change(
                    1,
                    2,
                    1,
                    1,
                    [_create_char_change(1, 4, 2, 5, 1, 4, 1, 5)],
                )
            ],
        )

    def test_two_lines_changed_2(self) -> None:
        """Middle two of four lines collapsed into one."""
        _do_assert_diff(
            ["foo", "abcd", "efgh", "BAR"],
            ["foo", "abcz", "BAR"],
            [
                _create_line_change(
                    2,
                    3,
                    2,
                    2,
                    [_create_char_change(2, 4, 3, 5, 2, 4, 2, 5)],
                )
            ],
        )

    def test_two_lines_changed_3(self) -> None:
        """Two lines changed: first line trimmed, second line prefixed."""
        _do_assert_diff(
            ["foo", "abcd", "efgh", "BAR"],
            ["foo", "abcz", "zzzzefgh", "BAR"],
            [
                _create_line_change(
                    2,
                    3,
                    2,
                    3,
                    [
                        _create_char_change(2, 4, 2, 5, 2, 4, 2, 5),
                        _create_char_change(3, 1, 3, 1, 3, 1, 3, 5),
                    ],
                )
            ],
        )

    def test_two_lines_changed_4(self) -> None:
        """Single line expanded into four lines (empty strings in between)."""
        _do_assert_diff(
            ["abc"],
            ["", "", "axc", ""],
            [
                _create_line_change(
                    1,
                    1,
                    1,
                    4,
                    [
                        _create_char_change(1, 1, 1, 1, 1, 1, 3, 1),
                        _create_char_change(1, 2, 1, 3, 3, 2, 3, 3),
                        _create_char_change(1, 4, 1, 4, 3, 4, 4, 1),
                    ],
                )
            ],
        )

    def test_empty_original_sequence_in_char_diff(self) -> None:
        """An empty original line expands to multiple modified lines -- no char changes."""
        _do_assert_diff(
            ["abc", "", "xyz"],
            ["abc", "qwe", "rty", "xyz"],
            [_create_line_change(2, 2, 2, 3)],
        )

    def test_three_lines_changed(self) -> None:
        """Three consecutive lines restructured into three new lines."""
        _do_assert_diff(
            ["foo", "abcd", "efgh", "BAR"],
            ["foo", "zzzefgh", "xxx", "BAR"],
            [
                _create_line_change(
                    2,
                    3,
                    2,
                    3,
                    [
                        _create_char_change(2, 1, 3, 1, 2, 1, 2, 4),
                        _create_char_change(3, 5, 3, 5, 2, 8, 3, 4),
                    ],
                )
            ],
        )

    def test_big_change_part_1(self) -> None:
        """Insertion at start + multi‑line change in the middle."""
        _do_assert_diff(
            ["foo", "abcd", "efgh", "BAR"],
            ["hello", "foo", "zzzefgh", "xxx", "BAR"],
            [
                _create_line_insertion(1, 1, 0),
                _create_line_change(
                    2,
                    3,
                    3,
                    4,
                    [
                        _create_char_change(2, 1, 3, 1, 3, 1, 3, 4),
                        _create_char_change(3, 5, 3, 5, 3, 8, 4, 4),
                    ],
                ),
            ],
        )

    def test_big_change_part_2(self) -> None:
        """Insertion + change + deletion in one diff."""
        _do_assert_diff(
            ["foo", "abcd", "efgh", "BAR", "RAB"],
            ["hello", "foo", "zzzefgh", "xxx", "BAR"],
            [
                _create_line_insertion(1, 1, 0),
                _create_line_change(
                    2,
                    3,
                    3,
                    4,
                    [
                        _create_char_change(2, 1, 3, 1, 3, 1, 3, 4),
                        _create_char_change(3, 5, 3, 5, 3, 8, 4, 4),
                    ],
                ),
                _create_line_deletion(5, 5, 5),
            ],
        )

    # -- Post‑processing -----------------------------------------------------

    def test_char_change_postprocessing_merges(self) -> None:
        """Char‑change post‑processing merges adjacent char changes."""
        _do_assert_diff(
            ["abba"],
            ["azzzbzzzbzzza"],
            [
                _create_line_change(
                    1,
                    1,
                    1,
                    1,
                    [_create_char_change(1, 2, 1, 4, 1, 2, 1, 13)],
                )
            ],
            should_compute_char_changes=True,
            should_post_process_char_changes=True,
        )

    # -- Trim‑whitespace mode ------------------------------------------------

    def test_ignore_trim_whitespace(self) -> None:
        """Leading/trailing whitespace ignored; char‑changes anchor on core text."""
        _do_assert_diff(
            ["\t\t foo ", "abcd", "efgh", "\t\t BAR\t\t"],
            ["  hello\t", "\t foo   \t", "zzzefgh", "xxx", "   BAR   \t"],
            [
                _create_line_insertion(1, 1, 0),
                _create_line_change(
                    2,
                    3,
                    3,
                    4,
                    [
                        _create_char_change(2, 1, 2, 5, 3, 1, 3, 4),
                        _create_char_change(3, 5, 3, 5, 4, 1, 4, 4),
                    ],
                ),
            ],
            should_compute_char_changes=True,
            should_ignore_trim_whitespace=True,
        )

    # -- Regression / issue tests --------------------------------------------

    def test_issue_12122_hasownproperty(self) -> None:
        """Regression: `hasOwnProperty` used as a line value caused crashes."""
        _do_assert_diff(
            ["hasOwnProperty"],
            ["hasOwnProperty", "and another line"],
            [_create_line_insertion(2, 2, 1)],
        )

    # -- Empty‑diff edge cases -----------------------------------------------

    def test_empty_diff_1(self) -> None:
        """Empty original → single modified line."""
        _do_assert_diff(
            [""],
            ["something"],
            [_create_line_change(1, 1, 1, 1, None)],
            should_ignore_trim_whitespace=True,
        )

    def test_empty_diff_2(self) -> None:
        """Empty original → two modified lines."""
        _do_assert_diff(
            [""],
            ["something", "something else"],
            [_create_line_change(1, 1, 1, 2, None)],
            should_ignore_trim_whitespace=True,
        )

    def test_empty_diff_3(self) -> None:
        """Two original lines → empty modified."""
        _do_assert_diff(
            ["something", "something else"],
            [""],
            [_create_line_change(1, 2, 1, 1, None)],
            should_ignore_trim_whitespace=True,
            should_compute_char_changes=True,
        )

    def test_empty_diff_4(self) -> None:
        """Single original line → empty modified."""
        _do_assert_diff(
            ["something"],
            [""],
            [_create_line_change(1, 1, 1, 1, None)],
            should_ignore_trim_whitespace=True,
        )

    def test_empty_diff_5(self) -> None:
        """Both original and modified are empty strings."""
        _do_assert_diff(
            [""],
            [""],
            [],
            should_ignore_trim_whitespace=True,
        )

    # -- Pretty‑diff ------------------------------------------------------------------

    def test_pretty_diff_1(self) -> None:
        """Pretty‑diff: insert new test function block."""
        _do_assert_diff(
            [
                "suite(function () {",
                "\ttest1() {",
                "\t\tassert.ok(true);",
                "\t}",
                "",
                "\ttest2() {",
                "\t\tassert.ok(true);",
                "\t}",
                "});",
                "",
            ],
            [
                "// An insertion",
                "suite(function () {",
                "\ttest1() {",
                "\t\tassert.ok(true);",
                "\t}",
                "",
                "\ttest2() {",
                "\t\tassert.ok(true);",
                "\t}",
                "",
                "\ttest3() {",
                "\t\tassert.ok(true);",
                "\t}",
                "});",
                "",
            ],
            [
                _create_line_insertion(1, 1, 0),
                _create_line_insertion(10, 13, 8),
            ],
            should_ignore_trim_whitespace=True,
        )

    def test_pretty_diff_2(self) -> None:
        """Pretty‑diff: insert comment block + delete code block."""
        _do_assert_diff(
            [
                "// Just a comment",
                "",
                "function compute(a, b, c, d) {",
                "\tif (a) {",
                "\t\tif (b) {",
                "\t\t\tif (c) {",
                "\t\t\t\treturn 5;",
                "\t\t\t}",
                "\t\t}",
                "\t\t// These next lines will be deleted",
                "\t\tif (d) {",
                "\t\t\treturn -1;",
                "\t\t}",
                "\t\treturn 0;",
                "\t}",
                "}",
            ],
            [
                "// Here is an inserted line",
                "// and another inserted line",
                "// and another one",
                "// Just a comment",
                "",
                "function compute(a, b, c, d) {",
                "\tif (a) {",
                "\t\tif (b) {",
                "\t\t\tif (c) {",
                "\t\t\t\treturn 5;",
                "\t\t\t}",
                "\t\t}",
                "\t\treturn 0;",
                "\t}",
                "}",
            ],
            [
                _create_line_insertion(1, 3, 0),
                _create_line_deletion(10, 13, 12),
            ],
            should_ignore_trim_whitespace=True,
        )

    def test_pretty_diff_3(self) -> None:
        """Pretty‑diff: insert a method between two existing methods."""
        _do_assert_diff(
            [
                "class A {",
                "\t/**",
                "\t * m1",
                "\t */",
                "\tmethod1() {}",
                "",
                "\t/**",
                "\t * m3",
                "\t */",
                "\tmethod3() {}",
                "}",
            ],
            [
                "class A {",
                "\t/**",
                "\t * m1",
                "\t */",
                "\tmethod1() {}",
                "",
                "\t/**",
                "\t * m2",
                "\t */",
                "\tmethod2() {}",
                "",
                "\t/**",
                "\t * m3",
                "\t */",
                "\tmethod3() {}",
                "}",
            ],
            [_create_line_insertion(7, 11, 6)],
            should_ignore_trim_whitespace=True,
        )

    # -- Large regression tests ----------------------------------------------

    def test_issue_23636(self) -> None:
        """Regression: indentation change across 27 lines (post‑processed chars)."""
        original = [
            "if(!TextDrawLoad[playerid])",
            "{",
            "",
            "\tTextDrawHideForPlayer(playerid,TD_AppleJob[3]);",
            "\tTextDrawHideForPlayer(playerid,TD_AppleJob[4]);",
            "\tif(!AppleJobTreesType[AppleJobTreesPlayerNum[playerid]])",
            "\t{",
            "\t\tfor(new i=0;i<10;i++) if(StatusTD_AppleJobApples[playerid][i]) TextDrawHideForPlayer(playerid,TD_AppleJob[5+i]);",
            "\t}",
            "\telse",
            "\t{",
            "\t\tfor(new i=0;i<10;i++) if(StatusTD_AppleJobApples[playerid][i]) TextDrawHideForPlayer(playerid,TD_AppleJob[15+i]);",
            "\t}",
            "}",
            "else",
            "{",
            "\tTextDrawHideForPlayer(playerid,TD_AppleJob[3]);",
            "\tTextDrawHideForPlayer(playerid,TD_AppleJob[27]);",
            "\tif(!AppleJobTreesType[AppleJobTreesPlayerNum[playerid]])",
            "\t{",
            "\t\tfor(new i=0;i<10;i++) if(StatusTD_AppleJobApples[playerid][i]) TextDrawHideForPlayer(playerid,TD_AppleJob[28+i]);",
            "\t}",
            "\telse",
            "\t{",
            "\t\tfor(new i=0;i<10;i++) if(StatusTD_AppleJobApples[playerid][i]) TextDrawHideForPlayer(playerid,TD_AppleJob[38+i]);",
            "\t}",
            "}",
        ]
        modified = [
            "\tif(!TextDrawLoad[playerid])",
            "\t{",
            "\t",
            "\t\tTextDrawHideForPlayer(playerid,TD_AppleJob[3]);",
            "\t\tTextDrawHideForPlayer(playerid,TD_AppleJob[4]);",
            "\t\tif(!AppleJobTreesType[AppleJobTreesPlayerNum[playerid]])",
            "\t\t{",
            "\t\t\tfor(new i=0;i<10;i++) if(StatusTD_AppleJobApples[playerid][i]) TextDrawHideForPlayer(playerid,TD_AppleJob[5+i]);",
            "\t\t}",
            "\t\telse",
            "\t\t{",
            "\t\t\tfor(new i=0;i<10;i++) if(StatusTD_AppleJobApples[playerid][i]) TextDrawHideForPlayer(playerid,TD_AppleJob[15+i]);",
            "\t\t}",
            "\t}",
            "\telse",
            "\t{",
            "\t\tTextDrawHideForPlayer(playerid,TD_AppleJob[3]);",
            "\t\tTextDrawHideForPlayer(playerid,TD_AppleJob[27]);",
            "\t\tif(!AppleJobTreesType[AppleJobTreesPlayerNum[playerid]])",
            "\t\t{",
            "\t\t\tfor(new i=0;i<10;i++) if(StatusTD_AppleJobApples[playerid][i]) TextDrawHideForPlayer(playerid,TD_AppleJob[28+i]);",
            "\t\t}",
            "\t\telse",
            "\t\t{",
            "\t\t\tfor(new i=0;i<10;i++) if(StatusTD_AppleJobApples[playerid][i]) TextDrawHideForPlayer(playerid,TD_AppleJob[38+i]);",
            "\t\t}",
            "\t}",
        ]
        expected = [
            _create_line_change(
                1,
                27,
                1,
                27,
                [_create_char_change(i, 1, i, 1, i, 1, i, 2) for i in range(1, 28)],
            )
        ]
        _do_assert_diff(
            original,
            modified,
            expected,
            should_compute_char_changes=True,
            should_post_process_char_changes=True,
        )

    def test_issue_43922(self) -> None:
        """Regression: inline code snippet removal mid‑sentence."""
        _do_assert_diff(
            [
                " * `yarn [install]` -- Install project NPM dependencies. This is automatically done when you first create the project. You should only need to run this if you add dependencies in `package.json`.",
            ],
            [
                " * `yarn` -- Install project NPM dependencies. You should only need to run this if you add dependencies in `package.json`.",
            ],
            [
                _create_line_change(
                    1,
                    1,
                    1,
                    1,
                    [
                        _create_char_change(1, 9, 1, 19, 1, 9, 1, 9),
                        _create_char_change(1, 58, 1, 120, 1, 48, 1, 48),
                    ],
                )
            ],
            should_compute_char_changes=True,
            should_post_process_char_changes=True,
        )

    def test_issue_42751(self) -> None:
        """Regression: whitespace + single‑char change in adjacent lines."""
        _do_assert_diff(
            ["    1", "  2"],
            ["    1", "   3"],
            [
                _create_line_change(
                    2,
                    2,
                    2,
                    2,
                    [_create_char_change(2, 3, 2, 4, 2, 3, 2, 5)],
                )
            ],
            should_compute_char_changes=True,
            should_post_process_char_changes=True,
        )

    def test_does_not_give_character_changes(self) -> None:
        """When char‑changes are disabled, only line‑level changes are produced."""
        _do_assert_diff(
            ["    1", "  2", "A"],
            ["    1", "   3", " A"],
            [_create_line_change(2, 3, 2, 3)],
            should_compute_char_changes=False,
        )

    def test_issue_44422_less_than_ideal_diff(self) -> None:
        """Regression: large class with method insertion / deletion."""
        original = [
            "export class C {",
            "",
            "\tpublic m1(): void {",
            "\t\t{",
            "\t\t//2",
            "\t\t//3",
            "\t\t//4",
            "\t\t//5",
            "\t\t//6",
            "\t\t//7",
            "\t\t//8",
            "\t\t//9",
            "\t\t//10",
            "\t\t//11",
            "\t\t//12",
            "\t\t//13",
            "\t\t//14",
            "\t\t//15",
            "\t\t//16",
            "\t\t//17",
            "\t\t//18",
            "\t\t}",
            "\t}",
            "",
            "\tpublic m2(): void {",
            "\t\tif (a) {",
            "\t\t\tif (b) {",
            "\t\t\t\t//A1",
            "\t\t\t\t//A2",
            "\t\t\t\t//A3",
            "\t\t\t\t//A4",
            "\t\t\t\t//A5",
            "\t\t\t\t//A6",
            "\t\t\t\t//A7",
            "\t\t\t\t//A8",
            "\t\t\t}",
            "\t\t}",
            "",
            "\t\t//A9",
            "\t\t//A10",
            "\t\t//A11",
            "\t\t//A12",
            "\t\t//A13",
            "\t\t//A14",
            "\t\t//A15",
            "\t}",
            "",
            "\tpublic m3(): void {",
            "\t\tif (a) {",
            "\t\t\t//B1",
            "\t\t}",
            "\t\t//B2",
            "\t\t//B3",
            "\t}",
            "",
            "\tpublic m4(): boolean {",
            "\t\t//1",
            "\t\t//2",
            "\t\t//3",
            "\t\t//4",
            "\t}",
            "",
            "}",
        ]
        modified = [
            "export class C {",
            "",
            "\tconstructor() {",
            "",
            "",
            "",
            "",
            "\t}",
            "",
            "\tpublic m1(): void {",
            "\t\t{",
            "\t\t//2",
            "\t\t//3",
            "\t\t//4",
            "\t\t//5",
            "\t\t//6",
            "\t\t//7",
            "\t\t//8",
            "\t\t//9",
            "\t\t//10",
            "\t\t//11",
            "\t\t//12",
            "\t\t//13",
            "\t\t//14",
            "\t\t//15",
            "\t\t//16",
            "\t\t//17",
            "\t\t//18",
            "\t\t}",
            "\t}",
            "",
            "\tpublic m4(): boolean {",
            "\t\t//1",
            "\t\t//2",
            "\t\t//3",
            "\t\t//4",
            "\t}",
            "",
            "}",
        ]
        expected = [
            _create_line_change(2, 0, 3, 9),
            _create_line_change(25, 55, 31, 0),
        ]
        _do_assert_diff(original, modified, expected, should_compute_char_changes=False)

    def test_gives_preference_to_matching_longer_lines(self) -> None:
        """Duplicate short lines; LCS should prefer matching the longer BB line."""
        _do_assert_diff(
            ["A", "A", "BB", "C"],
            ["A", "BB", "A", "D", "E", "A", "C"],
            [
                _create_line_change(2, 2, 1, 0),
                _create_line_change(3, 0, 3, 6),
            ],
            should_compute_char_changes=False,
        )

    def test_issue_119051_prefer_fewer_diff_hunks(self) -> None:
        """Regression: empty lines matching; prefers fewer hunks."""
        _do_assert_diff(
            ["1", "", "", "2", ""],
            ["1", "", "1.5", "", "", "2", "", "3", ""],
            [
                _create_line_change(2, 0, 3, 4),
                _create_line_change(5, 0, 8, 9),
            ],
            should_compute_char_changes=False,
        )

    def test_issue_121436_part_1(self) -> None:
        """Regression: diff chunk contains unchanged line (with trim‑ignore)."""
        _do_assert_diff(
            ["if (cond) {", "    cmd", "}"],
            ["if (cond) {", "    if (other_cond) {", "        cmd", "    }", "}"],
            [
                _create_line_change(1, 0, 2, 2),
                _create_line_change(2, 0, 4, 4),
            ],
            should_compute_char_changes=False,
            should_ignore_trim_whitespace=True,
        )

    def test_issue_121436_part_2(self) -> None:
        """Regression: diff chunk contains unchanged line (no trim‑ignore)."""
        _do_assert_diff(
            ["if (cond) {", "    cmd", "}"],
            ["if (cond) {", "    if (other_cond) {", "        cmd", "    }", "}"],
            [
                _create_line_change(1, 0, 2, 2),
                _create_line_change(2, 2, 3, 3),
                _create_line_change(2, 0, 4, 4),
            ],
            should_compute_char_changes=False,
        )

    def test_issue_169552_leading_trailing_whitespace(self) -> None:
        """Regression: assertion error with both leading and trailing whitespace diffs."""
        _do_assert_diff(
            ["if True:", "    print(2)"],
            ["if True:", "\tprint(2) "],
            [
                _create_line_change(
                    2,
                    2,
                    2,
                    2,
                    [
                        _create_char_change(2, 1, 2, 5, 2, 1, 2, 2),
                        _create_char_change(2, 13, 2, 13, 2, 10, 2, 11),
                    ],
                )
            ],
            should_compute_char_changes=True,
        )

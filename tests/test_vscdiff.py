"""Unit tests for the vscodiff Python implementation.

Run with: pytest tests/ -v
"""

from __future__ import annotations

import pytest

from vscodiff.common.diff.diff import (
    Debug,
    DiffChangeHelper,
    LcsDiff,
    MyArray,
    Sequence,
    StringDiffSequence,
    string_diff,
)
from vscodiff.common.diff.diff_change import DiffChange, DiffResult


# ---------------------------------------------------------------------------
# DiffChange
# ---------------------------------------------------------------------------


class TestDiffChange:
    def test_create(self):
        dc = DiffChange(0, 3, 1, 2)
        assert dc.original_start == 0
        assert dc.original_length == 3
        assert dc.modified_start == 1
        assert dc.modified_length == 2

    def test_get_original_end(self):
        dc = DiffChange(0, 3, 0, 0)
        assert dc.get_original_end() == 3

    def test_get_modified_end(self):
        dc = DiffChange(0, 0, 1, 2)
        assert dc.get_modified_end() == 3

    def test_equality(self):
        a = DiffChange(0, 3, 1, 2)
        b = DiffChange(0, 3, 1, 2)
        c = DiffChange(0, 2, 1, 2)
        assert a == b
        assert a != c


# ---------------------------------------------------------------------------
# DiffResult
# ---------------------------------------------------------------------------


class TestDiffResult:
    def test_create(self):
        changes = [DiffChange(0, 1, 0, 1)]
        dr = DiffResult(quit_early=False, changes=changes)
        assert dr.quit_early is False
        assert len(dr.changes) == 1
        assert dr.changes[0] == changes[0]

    def test_quit_early(self):
        dr = DiffResult(quit_early=True, changes=[])
        assert dr.quit_early is True
        assert dr.changes == []

    def test_empty_changes(self):
        dr = DiffResult(quit_early=False, changes=[])
        assert dr.changes == []
        assert dr.quit_early is False


# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------


class TestDebug:
    def test_assert_passes(self):
        Debug.assert_(True, "should not raise")

    def test_assert_fails(self):
        with pytest.raises(ValueError, match="test error"):
            Debug.assert_(False, "test error")


# ---------------------------------------------------------------------------
# MyArray
# ---------------------------------------------------------------------------


class TestMyArray:
    def test_copy(self):
        src = [1, 2, 3, 4, 5]
        dst = [0] * 5
        MyArray.copy(src, 0, dst, 0, 3)
        assert dst == [1, 2, 3, 0, 0]

    def test_copy_with_offset(self):
        src = [10, 20, 30, 40]
        dst = [0] * 6
        MyArray.copy(src, 1, dst, 2, 2)
        assert dst == [0, 0, 20, 30, 0, 0]

    def test_copy_full(self):
        src = [1, 2, 3]
        dst = [0] * 3
        MyArray.copy(src, 0, dst, 0, 3)
        assert dst == [1, 2, 3]


# ---------------------------------------------------------------------------
# DiffChangeHelper
# ---------------------------------------------------------------------------


class TestDiffChangeHelper:
    def test_empty(self):
        helper = DiffChangeHelper()
        changes = helper.get_changes()
        assert changes == []

    def test_single_original_addition_then_mark(self):
        helper = DiffChangeHelper()
        helper.add_original_element(0, 0)
        helper.mark_next_change()
        changes = helper.get_changes()
        assert len(changes) == 1
        assert changes[0].original_start == 0
        assert changes[0].original_length == 1
        assert changes[0].modified_start == 0
        assert changes[0].modified_length == 0

    def test_single_modified_addition_then_mark(self):
        helper = DiffChangeHelper()
        helper.add_modified_element(0, 0)
        helper.mark_next_change()
        changes = helper.get_changes()
        assert len(changes) == 1
        assert changes[0].original_start == 0
        assert changes[0].original_length == 0
        assert changes[0].modified_start == 0
        assert changes[0].modified_length == 1

    def test_multiple_changes(self):
        helper = DiffChangeHelper()
        helper.add_original_element(0, 0)
        helper.mark_next_change()
        helper.add_modified_element(1, 1)
        helper.add_modified_element(1, 2)
        helper.mark_next_change()
        changes = helper.get_changes()
        assert len(changes) == 2

    def test_auto_finalize_on_get_changes(self):
        helper = DiffChangeHelper()
        helper.add_original_element(0, 0)
        changes = helper.get_changes()
        assert len(changes) == 1

    def test_get_reverse_changes(self):
        helper = DiffChangeHelper()
        helper.add_original_element(0, 0)
        helper.mark_next_change()
        helper.add_modified_element(2, 2)
        helper.mark_next_change()
        changes = helper.get_reverse_changes()
        assert len(changes) == 2
        # reversed order: second change first
        assert changes[0].modified_start == 2


# ---------------------------------------------------------------------------
# StringDiffSequence
# ---------------------------------------------------------------------------


class TestStringDiffSequence:
    def test_empty_string(self):
        seq = StringDiffSequence("")
        elements = seq.get_elements()
        assert len(elements) == 0

    def test_simple_string(self):
        seq = StringDiffSequence("abc")
        elements = seq.get_elements()
        assert elements == [ord("a"), ord("b"), ord("c")]

    def test_get_strict_element(self):
        seq = StringDiffSequence("hello")
        assert seq.get_strict_element(0) == "h"
        assert seq.get_strict_element(4) == "o"


# ---------------------------------------------------------------------------
# LcsDiff
# ---------------------------------------------------------------------------


class TestLcsDiff:
    def _compute(self, original: str, modified: str) -> list[DiffChange]:
        result = LcsDiff(
            StringDiffSequence(original), StringDiffSequence(modified)
        ).compute_diff(pretty=False)
        return result.changes

    def test_identical_strings(self):
        changes = self._compute("abc", "abc")
        assert len(changes) == 0

    def test_insertion_at_start(self):
        changes = self._compute("bc", "abc")
        assert len(changes) == 1
        assert changes[0].original_length == 0
        assert changes[0].modified_length == 1  # 'a' inserted

    def test_insertion_at_end(self):
        changes = self._compute("ab", "abc")
        assert len(changes) == 1
        assert changes[0].modified_length == 1

    def test_deletion_at_start(self):
        changes = self._compute("abc", "bc")
        assert len(changes) == 1
        assert changes[0].original_length == 1  # 'a' deleted
        assert changes[0].modified_length == 0

    def test_deletion_at_end(self):
        changes = self._compute("abc", "ab")
        assert len(changes) == 1
        assert changes[0].original_length == 1

    def test_modification(self):
        changes = self._compute("abc", "axc")
        assert len(changes) == 1
        # one char deleted + one inserted
        assert changes[0].original_length == 1
        assert changes[0].modified_length == 1

    def test_complete_replacement(self):
        changes = self._compute("abc", "xyz")
        assert len(changes) == 1
        assert changes[0].original_length == 3
        assert changes[0].modified_length == 3

    def test_empty_original(self):
        changes = self._compute("", "abc")
        assert len(changes) == 1
        assert changes[0].original_length == 0
        assert changes[0].modified_length == 3

    def test_empty_modified(self):
        changes = self._compute("abc", "")
        assert len(changes) == 1
        assert changes[0].original_length == 3
        assert changes[0].modified_length == 0

    def test_both_empty(self):
        changes = self._compute("", "")
        assert len(changes) == 0

    def test_multi_change(self):
        # "abc" -> "axbc" = insertion of 'x' between b and c
        changes = self._compute("abc", "axbc")
        # single change: insert 'x'
        assert len(changes) == 1
        assert changes[0].original_length == 0  # just insert
        assert changes[0].modified_length == 1

    def test_string_diff_function(self):
        changes = string_diff("abc", "axc", pretty=False)
        assert len(changes) == 1
        assert isinstance(changes[0], DiffChange)

    def test_string_diff_pretty(self):
        changes = string_diff("abc", "axc", pretty=True)
        assert isinstance(changes, list)
        assert all(isinstance(c, DiffChange) for c in changes)


# ---------------------------------------------------------------------------
# Sequence ABC
# ---------------------------------------------------------------------------


class TestSequence:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Sequence()  # type: ignore


# ---------------------------------------------------------------------------
# Integration: LcsDiff with multi-line text
# ---------------------------------------------------------------------------


class TestLcsDiffMultiline:
    MULTI_A = "line1\nline2\nline3\n"
    MULTI_B = "line1\nline2_changed\nline3\nline4\n"

    def test_multiline_diff(self):
        changes = (
            LcsDiff(StringDiffSequence(self.MULTI_A), StringDiffSequence(self.MULTI_B))
            .compute_diff(pretty=False)
            .changes
        )
        # Should have some changes
        assert len(changes) > 0


# ---------------------------------------------------------------------------
# VSCDiff (main entry point)
# ---------------------------------------------------------------------------


class TestVSCDiff:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from vscodiff.engine import VSCDiff

        self.VSCDiff = VSCDiff

    def test_create_instance(self):
        vsdiff = self.VSCDiff()
        assert vsdiff is not None

    def test_identical_strings(self):
        vsdiff = self.VSCDiff()
        result = vsdiff.compute_diff("same", "same")
        assert result.identical is True
        assert result.quit_early is False
        assert len(result.changes) == 0
        assert len(result.moves) == 0

    def test_simple_diff(self):
        vsdiff = self.VSCDiff()
        result = vsdiff.compute_diff(
            "one\ntwo\nthree\nfour\nfive",
            "one\nTwo\nThree\nfour\nfive\nSix",
        )
        assert not result.identical
        assert len(result.changes) > 0

    def test_empty_original(self):
        vsdiff = self.VSCDiff()
        result = vsdiff.compute_diff("", "hello\nworld")
        assert not result.identical
        assert len(result.changes) == 1

    def test_empty_modified(self):
        vsdiff = self.VSCDiff()
        result = vsdiff.compute_diff("hello\nworld", "")
        assert not result.identical
        assert len(result.changes) == 1

    def test_both_empty(self):
        vsdiff = self.VSCDiff()
        result = vsdiff.compute_diff("", "")
        assert result.identical is True
        assert result.changes == []

    def test_cache_hit(self):
        vsdiff = self.VSCDiff()
        r1 = vsdiff.compute_diff("abc", "abd")
        r2 = vsdiff.compute_diff("abc", "abd")  # cache hit
        assert len(r1.changes) == len(r2.changes)

    def test_with_legacy_algorithm(self):
        from vscodiff.engine import DiffOptions

        vsdiff = self.VSCDiff()
        legacy_opts = DiffOptions(
            ignore_trim_whitespace=True,
            max_computation_time_ms=1000,
            compute_moves=False,
            diff_algorithm="legacy",
        )
        result = vsdiff.compute_diff("abc", "abd", legacy_opts)
        assert result is not None
        assert len(result.changes) > 0

    def test_vscdiff_options_constructor(self):
        from vscodiff.engine import VSCDiffOptions, DiffOptions

        opts = VSCDiffOptions(
            diff_options=DiffOptions(
                diff_algorithm="advanced",
                ignore_trim_whitespace=False,
            ),
            cache_size=50,
        )
        vsdiff = self.VSCDiff(opts)
        result = vsdiff.compute_diff("abc", "abd")
        assert result is not None

    def test_complex_diff_from_ts_suite(self):
        """Port of the TS complex case snapshot test."""
        original = (
            "for (let i722 = 0; i722 < 7; i722++) { /* loop */ }\n"
            "    const fn114 = () => ['4f7omf', 'yq7ukl', 27];\n"
            "    console.log('dunrt');\n"
            "    const obj259 = { prop: { key: { key: 'yk4pen' } } };\n"
            "    const fn719 = () => { key: 'wry0ki' };\n"
            "    console.log('0t7o5');\n"
            "    for (let i139 = 0; i139 < 7; i139++) { /* loop */ }\n"
            "    console.log('112sqm');\n"
            "    function func387(a, b) { return a + b || 0; }\n"
            "    let var276 = { key: 54 };\n"
            "    let var778 = '1x6xti';\n"
            "    const fn765 = () => 27;\n"
            "    function func544(a) { return a || 0; }\n"
            "    function func170(a, b) { return a + b || 0; }\n"
            "    if (var254 > 24) { /* condition */ }\n"
            "    if (var252 > 47) { /* condition */ }\n"
            "    if (var679 > 21) { /* condition */ }\n"
            "    const obj943 = { prop: ['lharbc', 'r3iag', 90] };\n"
            "    if (var818 > 6) { /* condition */ }\n"
            "    const fn771 = () => { key: { key: [{ key: '0yrfhj' }, 91, '3z09h'] } };\n"
            "    function func103(a) { return a || 0; }\n"
            "    function func641(a) { return a || 0; }\n"
            "    var71 = 16;\n"
            "    function func21(a) { return a || 0; }\n"
            "    if (var924 > 25) { /* condition */ }\n"
            "    const obj582 = { prop: 49 };\n"
            "    for (let i905 = 0; i905 < 1; i905++) { /* loop */ }\n"
            "    var522 = 5;\n"
            "    var349 = { key: { key: 'hnx7g' } };\n"
            "    let var808 = [40, 'nrp50i', [29, 61, '2it09r']];"
        )
        modified = (
            "for (let i722 = 0; i722 < 7; i722++) { /* loop */ }\n"
            "    function func374(a) { return a || 0; }\n"
            "    const fn946 = () => 'o5abb2c';\n"
            "    const obj256 = { prop: { key: 20 } };\n"
            "    const fn114 = () => ['4f7omf', 'yq7ukl', 27];\n"
            "    console.log('dunrt');\n"
            "    const obj259 = { prop: { key: { key: 'yk4pen' } } };\n"
            "    const obj724 = { prop: { key: 'qeabja' } };\n"
            "    const fn719 = () => { key: 'wry0ki' };\n"
            "    console.log('0t7o5');\n"
            "    function func126(a, b) { return a + b || 0; }\n"
            "    const fn158 = () => { key: 'gxyikw' };\n"
            "    function func152(a, b) { return a + b || 0; }\n"
            "    for(leti139=0;i139<29;i139++){/*loop*/}\n"
            "    for (let i182 = 0; i182 < 2; i182++) { /* loop */ }\n"
            "    functionfunc387(a,b){returna+b||49;}\n"
            "    let var276 = { key: 54 };\n"
            "    letvar404='1x6xti';\n"
            "    const fn765 = () => 27;\n"
            "    functionfunc544(a){returna||61;}\n"
            "    functionfunc170(a,b){returna+b||71;}\n"
            "    if (var254 > 24) { /* condition */ }\n"
            "    if (var252 > 47) { /* condition */ }\n"
            "    if (var499 > 23) { /* condition */ }\n"
            "    if (var679 > 21) { /* condition */ }\n"
            "    if (var818 > 6) { /* condition */ }\n"
            "    const fn771 = () => { key: { key: [{ key: '0yrfhj' }, 91, '3z09h'] } };\n"
            "    functionfunc103(a){returna||58;}\n"
            "    if (var538 > 34) { /* condition */ }\n"
            "    function func21(a) { return a || 0; }\n"
            "    if (var924 > 25) { /* condition */ }\n"
            "    for (let i905 = 0; i905 < 1; i905++) { /* loop */ }\n"
            "    var522 = 5;\n"
            "    var349 = { key: { key: 'hnx7g' } };\n"
            "    let var808 = [40, 'nrp50i', [29, 61, '2it09r']];"
        )
        vsdiff = self.VSCDiff()
        result = vsdiff.compute_diff(original, modified)
        assert result is not None
        assert not result.identical
        assert len(result.changes) > 0


# ---------------------------------------------------------------------------
# LineSequence
# ---------------------------------------------------------------------------


class TestLineSequence:
    def test_create(self):
        from vscodiff.diff.default_lines_diff_computer.line_sequence import (
            LineSequence,
        )

        seq = LineSequence([1, 2, 3], ["line1", "line2", "line3"])
        assert seq.length == 3

    def test_get_element_empty(self):
        from vscodiff.diff.default_lines_diff_computer.line_sequence import (
            LineSequence,
        )

        seq = LineSequence([10, 20], ["a", "b"])
        assert seq.get_element(0) == 10
        assert seq.get_element(1) == 20


# ---------------------------------------------------------------------------
# LinesSliceCharSequence
# ---------------------------------------------------------------------------


class TestLinesSliceCharSequence:
    def test_create(self):
        from vscodiff.common.range import Range
        from vscodiff.diff.default_lines_diff_computer.lines_slice_char_sequence import (
            LinesSliceCharSequence,
        )

        seq = LinesSliceCharSequence(["abc", "def"], Range(1, 1, 2, 4), False)
        assert seq.length > 0

    def test_empty(self):
        from vscodiff.common.range import Range
        from vscodiff.diff.default_lines_diff_computer.lines_slice_char_sequence import (
            LinesSliceCharSequence,
        )

        # Range with same start/end line yields empty sequence
        seq = LinesSliceCharSequence(["abc"], Range(1, 1, 1, 1), False)
        assert seq.length == 0

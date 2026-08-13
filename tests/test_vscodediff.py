"""Tests for the VSCodeDiff public entry point.

Run with: pytest tests/ -v
"""

from __future__ import annotations

import pytest

from vscodiff.engine import DiffOptions, VSCodeDiff, VSCodeDiffOptions


class TestVSCodeDiff:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.VSCodeDiff = VSCodeDiff

    # A text pair where a 5-line block is moved and a line is inserted, so
    # that compute_moves=True detects a move.
    MOVED_BLOCK_ORIGINAL = "\n".join(
        ["def setup():"]
        + [f"    alpha_{i} = compute_alpha({i})" for i in range(5)]
        + [f"    beta_{i} = compute_beta({i})" for i in range(5)]
        + ["    return done"]
    )
    MOVED_BLOCK_MODIFIED = "\n".join(
        ["def setup():"]
        + [f"    beta_{i} = compute_beta({i})" for i in range(5)]
        + ["    gamma = 1"]
        + [f"    alpha_{i} = compute_alpha({i})" for i in range(5)]
        + ["    return done"]
    )

    def test_create_instance(self):
        vsdiff = self.VSCodeDiff()
        assert vsdiff is not None

    def test_identical_strings(self):
        vsdiff = self.VSCodeDiff()
        result = vsdiff.compute_diff("same", "same")
        assert result.identical is True
        assert result.quit_early is False
        assert len(result.changes) == 0
        assert len(result.moves) == 0

    def test_simple_diff(self):
        vsdiff = self.VSCodeDiff()
        result = vsdiff.compute_diff(
            "one\ntwo\nthree\nfour\nfive",
            "one\nTwo\nThree\nfour\nfive\nSix",
        )
        assert not result.identical
        assert len(result.changes) > 0

    def test_empty_original(self):
        vsdiff = self.VSCodeDiff()
        result = vsdiff.compute_diff("", "hello\nworld")
        assert not result.identical
        assert len(result.changes) == 1

    def test_empty_modified(self):
        vsdiff = self.VSCodeDiff()
        result = vsdiff.compute_diff("hello\nworld", "")
        assert not result.identical
        assert len(result.changes) == 1

    def test_both_empty(self):
        vsdiff = self.VSCodeDiff()
        result = vsdiff.compute_diff("", "")
        assert result.identical is True
        assert result.changes == []

    def test_cache_hit(self):
        vsdiff = self.VSCodeDiff()
        r1 = vsdiff.compute_diff("abc", "abd")
        r2 = vsdiff.compute_diff("abc", "abd")  # cache hit
        assert len(r1.changes) == len(r2.changes)

    def test_cache_respects_options(self):
        # Regression test: the cache key must include the effective options,
        # otherwise a second call with different options would return the
        # stale cached result of the first call.
        vsdiff = self.VSCodeDiff()
        no_moves = vsdiff.compute_diff(
            self.MOVED_BLOCK_ORIGINAL,
            self.MOVED_BLOCK_MODIFIED,
            DiffOptions(compute_moves=False),
        )
        with_moves = vsdiff.compute_diff(
            self.MOVED_BLOCK_ORIGINAL,
            self.MOVED_BLOCK_MODIFIED,
            DiffOptions(compute_moves=True),
        )
        assert len(no_moves.moves) == 0
        assert len(with_moves.moves) > 0

    def test_compute_moves(self):
        vsdiff = self.VSCodeDiff()
        result = vsdiff.compute_diff(
            self.MOVED_BLOCK_ORIGINAL,
            self.MOVED_BLOCK_MODIFIED,
            DiffOptions(compute_moves=True),
        )
        assert len(result.moves) > 0
        move = result.moves[0]
        assert not move.line_range_mapping.original.is_empty
        assert not move.line_range_mapping.modified.is_empty

    def test_compute_moves_disabled_by_default(self):
        vsdiff = self.VSCodeDiff()
        result = vsdiff.compute_diff(
            self.MOVED_BLOCK_ORIGINAL, self.MOVED_BLOCK_MODIFIED
        )
        assert len(result.moves) == 0

    def test_extend_to_subwords(self):
        original = "abcDefg = 1;"
        modified = "abcXefg = 1;"
        vsdiff = self.VSCodeDiff()

        def inner_ranges(extend_to_subwords: bool):
            result = vsdiff.compute_diff(
                original,
                modified,
                DiffOptions(extend_to_subwords=extend_to_subwords),
            )
            return [
                (ic.original_range, ic.modified_range)
                for c in result.changes
                for ic in (c.inner_changes or [])
            ]

        plain = inner_ranges(False)
        subwords = inner_ranges(True)
        assert plain != subwords
        # Extending to subwords widens the changed character range.
        [(plain_orig, _)] = plain
        [(sub_orig, _)] = subwords
        assert sub_orig.end.column > plain_orig.end.column

    def test_max_computation_time_ms_zero_disables_timeout(self):
        # max_computation_time_ms=0 maps to an infinite timeout, so even a
        # non-trivial diff completes without quitting early.
        original = "\n".join(f"original line {i}" for i in range(200))
        modified = "\n".join(f"modified line {i}" for i in range(200))
        vsdiff = self.VSCodeDiff()
        result = vsdiff.compute_diff(
            original, modified, DiffOptions(max_computation_time_ms=0)
        )
        assert result.quit_early is False
        assert len(result.changes) > 0

    def test_with_legacy_algorithm(self):
        vsdiff = self.VSCodeDiff()
        legacy_opts = DiffOptions(
            ignore_trim_whitespace=True,
            max_computation_time_ms=1000,
            compute_moves=False,
            diff_algorithm="legacy",
        )
        result = vsdiff.compute_diff("abc", "abd", legacy_opts)
        assert result is not None
        assert len(result.changes) > 0

    def test_legacy_and_advanced_both_compute(self):
        vsdiff = self.VSCodeDiff()
        original = "one\ntwo\nthree\nfour\nfive"
        modified = "one\nTwo\nthree\nfive\nsix"
        advanced = vsdiff.compute_diff(
            original, modified, DiffOptions(diff_algorithm="advanced")
        )
        legacy = vsdiff.compute_diff(
            original, modified, DiffOptions(diff_algorithm="legacy")
        )
        assert not advanced.identical
        assert not legacy.identical
        assert len(advanced.changes) > 0
        assert len(legacy.changes) > 0

    def test_vscdiff_options_constructor(self):
        opts = VSCodeDiffOptions(
            diff_options=DiffOptions(
                diff_algorithm="advanced",
                ignore_trim_whitespace=False,
            ),
            cache_size=50,
        )
        vsdiff = self.VSCodeDiff(opts)
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
            "    const fn158 = { key: 'gxyikw' };\n"
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
        vsdiff = self.VSCodeDiff()
        result = vsdiff.compute_diff(original, modified)
        assert result is not None
        assert not result.identical
        assert len(result.changes) > 0

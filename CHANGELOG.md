# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- The diff cache key now includes the effective diff options, so `compute_diff` calls with the same texts but different options (e.g. `compute_moves`) no longer wrongly hit the cache
- Fixed several advanced-algorithm porting bugs uncovered by the VS Code diffing fixtures: `SequenceDiff.intersect` dropped pure insertion/deletion character diffs, `LineRange.intersect` computed a wrong start line, move detection crashed on unhashable changes and on division by zero in line similarity, and the Myers algorithm now mirrors JS `undefined`/`NaN` array-read semantics instead of raising `IndexError`

### Changed

- **Breaking:** Renamed `VSCDiff` to `VSCodeDiff` and `VSCDiffOptions` to `VSCodeDiffOptions`
- **Breaking:** Narrowed the public interface to `VSCodeDiff`, `VSCodeDiffOptions`, `DiffOptions`, `DocumentDiff`, and the diff result types (`DetailedLineRangeMapping`, `LineRangeMapping`, `RangeMapping`, `MovedText`, `LineRange`, `Position`, `Range`); algorithm internals remain importable from their submodules

### Removed

- **Breaking:** Removed dead modules carried over from the VS Code port: `TextModel` / `GetValueOptions`, `DocumentDiffProvider` / `null_document_diff`, `SingleEditOperation`, `OffsetEdit` / `SingleOffsetEdit`, `PositionOffsetTransformer`, `StringText` / `TextEdit` / `SingleTextEdit`, and `common_prefix_length` / `common_suffix_length`
- `DocumentDiff` and the diff options now live in `vscodiff.engine`; `DiffOptions` no longer inherits `DocumentDiffProviderOptions`

## [0.1.0] - 2025-04-28

### Added

- Initial release
- `VSCDiff` main diff engine with `VSCDiffOptions` configuration
- Myers diff algorithm (`O(ND)` difference) implementation
- Line-level diff with subword refinement
- Character-level diff within changed lines (`RangeMapping`, `DetailedLineRangeMapping`)
- Timeout-aware computation (`max_computation_time_ms`)
- LRU cache for repeated diff requests (`cache_size`)
- Move detection support (`compute_moves`)
- Multiple diff algorithms: `advanced`, `balanced`, `greedy`, `lcs`
- Ignore trim whitespace option
- Full type annotations with `py.typed` marker
- `DocumentDiff` result type with `identical`, `quit_early`, `changes`, `moves` fields
- Comprehensive test suite with 128 test cases (including VS Code's own diff test suite)

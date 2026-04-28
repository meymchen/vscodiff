# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

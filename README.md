# vscodiff

Python implementation of VS Code's diff algorithm, ported from TypeScript [codiff](https://github.com/zhanba/codiff).

## Features

- Myers diff algorithm (`O(ND)` difference)
- Line-level diff with subword refinement
- Timeout-aware computation (set max time per diff)
- LRU cache for repeated diff requests
- Move detection support
- Type-safe — fully typed with `py.typed` marker

## Installation

```bash
pip install vscodiff
```

Requires Python ≥ 3.12.

## Quick Start

```python
from vscodiff import Codiff, DiffOptions

codiff = Codiff()

# Compute diff between two strings
result = codiff.compute_diff("hello\nworld", "hello\nthere\nworld")

for change in result.changes:
    print(f"  original lines {change.original}: {change.inner_changes}")
```

## API

### `Codiff`

Main diff entry point. Configure with `CodiffOptions`:

```python
from vscodiff import Codiff, CodiffOptions, DiffOptions

options = CodiffOptions(
    diff_options=DiffOptions(
        ignore_trim_whitespace=True,
        max_computation_time_ms=1000,
        compute_moves=False,
        diff_algorithm="advanced",
    ),
    cache_size=100,
)
codiff = Codiff(options)
result = codiff.compute_diff(original_text, modified_text)
```

### Key Types

| Type | Description |
|------|-------------|
| `Codiff` | Main diff engine |
| `DocumentDiff` | Result: identical, quit_early, changes, moves |
| `DetailedLineRangeMapping` | A changed line range with inner char-level diffs |
| `RangeMapping` | Character-level diff range |
| `LinesDiff` | Raw line diff output (changes + moves + timeout) |

## License

MIT

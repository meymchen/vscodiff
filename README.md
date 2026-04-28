# vscodiff

Python implementation of VS Code's diff algorithm, referenced from the VS Code source code.

## Features

- Myers diff algorithm (`O(ND)` difference)
- Line-level diff with subword refinement
- Timeout-aware computation (set max time per diff)
- LRU cache for repeated diff requests
- Move detection support
- Type-safe — fully typed with `py.typed` marker

## Installation

**Recommended — with uv:**

```bash
uv add vscodiff
```

**Alternative — with pip:**

```bash
pip install vscodiff
```

Requires Python ≥ 3.12.

## Quick Start

```python
from vscodiff import VSCDiff, DiffOptions

diff = VSCDiff()

# Compute diff between two strings
result = diff.compute_diff("hello\nworld", "hello\nthere\nworld")

for change in result.changes:
    print(f"  original lines {change.original}: {change.inner_changes}")
```

## API

### `VSCDiff`

Main diff entry point. Configure with `VSCDiffOptions`:

```python
from vscodiff import VSCDiff, VSCDiffOptions, DiffOptions

options = VSCDiffOptions(
    diff_options=DiffOptions(
        ignore_trim_whitespace=True,
        max_computation_time_ms=1000,
        compute_moves=False,
        diff_algorithm="advanced",
    ),
    cache_size=100,
)
diff = VSCDiff(options)
result = diff.compute_diff(original_text, modified_text)
```

### Key Types

| Type | Description |
|------|-------------|
| `VSCDiff` | Main diff engine |
| `DocumentDiff` | Result: identical, quit_early, changes, moves |
| `DetailedLineRangeMapping` | A changed line range with inner char-level diffs |
| `RangeMapping` | Character-level diff range |
| `LinesDiff` | Raw line diff output (changes + moves + timeout) |

## License

MIT

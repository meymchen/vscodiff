"""Fixture-based diffing tests ported from VS Code's fixtures.test.ts.

Each folder under tests/fixtures/ contains a `1.*` file (original text), a `2.*`
file (modified text) and an `advanced.expected.diff.json` golden file produced
by VS Code's DefaultLinesDiffComputer. This runner recomputes the diff with the
Python port and compares the serialized result against the golden file.

Source of the upstream runner:
https://github.com/microsoft/vscode/blob/main/src/vs/editor/test/node/diffing/fixtures.test.ts
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vscodiff.common.line_range import LineRange
from vscodiff.common.position import Position
from vscodiff.common.range import Range
from vscodiff.diff.default_lines_diff_computer.default_lines_diff_computer import (
    DefaultLineDiffComputer,
)
from vscodiff.diff.lines_diff_computer import (
    LinesDiff,
    LinesDiffComputerOptions,
)
from vscodiff.diff.range_mapping import DetailedLineRangeMapping, RangeMapping

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _fixture_folders() -> list[str]:
    return sorted(p.name for p in FIXTURES_DIR.iterdir() if p.is_dir())


def _read_content(path: Path) -> str:
    # Match the upstream normalization: \r\n and \r become \n.
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def _format_line_range(line_range: LineRange) -> str:
    # VS Code's LineRange.toString(): "[startLineNumber,endLineNumberExclusive)"
    return f"[{line_range.start_line},{line_range.end_line_exclusive})"


def _format_range(range_: Range, lines: list[str]) -> str:
    # Port of formatRange() in fixtures.test.ts.
    to_last_char = range_.end_column == len(lines[range_.end_line - 1]) + 1
    return (
        f"[{range_.start_line},{range_.start_column}"
        f" -> {range_.end_line},{range_.end_column}"
        f"{' EOL' if to_last_char else ''}]"
    )


def _assert_range_mappings_sorted(range_mappings: list[RangeMapping]) -> None:
    # Port of RangeMapping.assertSorted().
    for previous, current in zip(range_mappings, range_mappings[1:]):
        assert previous.original_range.end <= current.original_range.start
        assert previous.modified_range.end <= current.modified_range.start


def _get_diffs(
    changes: list[DetailedLineRangeMapping],
    original_lines: list[str],
    modified_lines: list[str],
) -> list[dict]:
    for c in changes:
        _assert_range_mappings_sorted(c.inner_changes or [])

    return [
        {
            "originalRange": _format_line_range(c.original),
            "modifiedRange": _format_line_range(c.modified),
            "innerChanges": [
                {
                    "originalRange": _format_range(ic.original_range, original_lines),
                    "modifiedRange": _format_range(ic.modified_range, modified_lines),
                }
                for ic in c.inner_changes
            ]
            if c.inner_changes is not None
            else None,
        }
        for c in changes
    ]


def _position_to_offset(lines: list[str], position: Position) -> int:
    offset = sum(len(line) + 1 for line in lines[: position.line - 1])
    return offset + position.column - 1


def _get_value_of_range(lines: list[str], range_: Range) -> str:
    text = "\n".join(lines)
    start = _position_to_offset(lines, range_.start)
    end = _position_to_offset(lines, range_.end)
    return text[start:end]


def _assert_diff_correctness(
    diff: LinesDiff, original_lines: list[str], modified_lines: list[str]
) -> None:
    """Port of assertDiffCorrectness() in fixtures.test.ts.

    Applying all inner changes to the original text must reproduce the
    modified text. Changes must be sorted and non-overlapping.
    """
    previous: DetailedLineRangeMapping | None = None
    for c in diff.changes:
        if previous is not None:
            assert previous.original.end_line_exclusive <= c.original.start_line
            assert previous.modified.end_line_exclusive <= c.modified.start_line
        previous = c

    replacements: list[tuple[int, int, str]] = []
    for c in diff.changes:
        for ic in c.inner_changes or []:
            start = _position_to_offset(original_lines, ic.original_range.start)
            end = _position_to_offset(original_lines, ic.original_range.end)
            assert start <= end
            replacements.append(
                (start, end, _get_value_of_range(modified_lines, ic.modified_range))
            )

    result = "\n".join(original_lines)
    # Inner changes are sorted and non-overlapping. Apply them from last to
    # first so that earlier offsets stay valid; for insertions at the same
    # position, the later-listed change is applied first, matching the order
    # produced by TextEdit.normalize() upstream.
    for start, end, new_text in reversed(replacements):
        result = result[:start] + new_text + result[end:]

    assert result == "\n".join(modified_lines)


def _run_fixture(folder: str) -> dict:
    folder_path = FIXTURES_DIR / folder
    file_names = [p.name for p in folder_path.iterdir()]

    first_file_name = next(f for f in file_names if f.startswith("1."))
    second_file_name = next(f for f in file_names if f.startswith("2."))

    original_content = _read_content(folder_path / first_file_name)
    original_lines = original_content.split("\n")
    modified_content = _read_content(folder_path / second_file_name)
    modified_lines = modified_content.split("\n")

    ignore_trim_whitespace = "trimws" in folder

    diff = DefaultLineDiffComputer().compute_diff(
        original_lines,
        modified_lines,
        LinesDiffComputerOptions(
            ignore_trim_whitespace=ignore_trim_whitespace,
            max_computation_time_ms=10**15,
            compute_moves=True,
            extend_to_subwords=None,
        ),
    )

    if not ignore_trim_whitespace:
        _assert_diff_correctness(diff, original_lines, modified_lines)

    actual: dict = {
        "original": {"content": original_content, "fileName": f"./{first_file_name}"},
        "modified": {
            "content": modified_content,
            "fileName": f"./{second_file_name}",
        },
        "diffs": _get_diffs(diff.changes, original_lines, modified_lines),
        "moves": [
            {
                "originalRange": _format_line_range(m.line_range_mapping.original),
                "modifiedRange": _format_line_range(m.line_range_mapping.modified),
                "changes": _get_diffs(m.changes, original_lines, modified_lines),
            }
            for m in diff.moves
        ],
    }
    if len(actual["moves"]) == 0:
        del actual["moves"]

    return actual


@pytest.mark.parametrize("folder", _fixture_folders())
def test_diffing_fixture(folder: str):
    expected_path = FIXTURES_DIR / folder / "advanced.expected.diff.json"
    assert expected_path.exists(), f"missing golden file: {expected_path}"

    actual = _run_fixture(folder)
    expected = json.loads(expected_path.read_bytes().decode("utf-8"))

    assert actual == expected

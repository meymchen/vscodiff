from __future__ import annotations

import array
import re
from abc import ABC, abstractmethod
from typing import Callable, cast

from vscodiff.common.hash import string_hash
from vscodiff.common.uint import Constants
from vscodiff.common.diff.diff_change import DiffChange, DiffResult


class Sequence(ABC):
    @abstractmethod
    def get_elements(self) -> array.array[int] | list[int] | list[str]: ...

    @abstractmethod
    def get_strict_element(self, index: int) -> str: ...


class StringDiffSequence(Sequence):
    def __init__(self, source: str):
        super().__init__()

        self._source = source

    def get_elements(self) -> list[int]:
        source = self._source
        return [ord(ch) for ch in source]

    def get_strict_element(self, index: int) -> str:
        return self._source[index]


# ---------------------------------------------------------------------------
# Ported from VSCode's LcsDiff.cs (via TypeScript)
# ---------------------------------------------------------------------------

_MAX_DIFFERENCES_HISTORY = 1447


class Debug:
    @staticmethod
    def assert_(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(message)


class MyArray:
    @staticmethod
    def copy(
        source_array: list,
        source_index: int,
        destination_array: list,
        destination_index: int,
        length: int,
    ) -> None:
        for i in range(length):
            destination_array[destination_index + i] = source_array[source_index + i]


class DiffChangeHelper:
    """A utility class which helps to create the set of DiffChanges from
    a difference operation. This class accepts original DiffElements and
    modified DiffElements that are involved in a particular change. The
    mark_next_change() method can be called to mark the separation between
    distinct changes. At the end, the changes property can be called to retrieve
    the constructed changes."""

    def __init__(self) -> None:
        self._changes: list[DiffChange] = []
        self._original_start: int = int(Constants.MAX_SAFE_SMALL_INT)
        self._modified_start: int = int(Constants.MAX_SAFE_SMALL_INT)
        self._original_count: int = 0
        self._modified_count: int = 0

    def mark_next_change(self) -> None:
        """Marks the beginning of the next change in the set of differences."""
        if self._original_count > 0 or self._modified_count > 0:
            self._changes.append(
                DiffChange(
                    self._original_start,
                    self._original_count,
                    self._modified_start,
                    self._modified_count,
                )
            )

        self._original_count = 0
        self._modified_count = 0
        self._original_start = int(Constants.MAX_SAFE_SMALL_INT)
        self._modified_start = int(Constants.MAX_SAFE_SMALL_INT)

    def add_original_element(self, original_index: int, modified_index: int) -> None:
        """Adds the original element at the given position to the elements
        affected by the current change. The modified index gives context
        to the change position with respect to the original sequence."""
        self._original_start = min(self._original_start, original_index)
        self._modified_start = min(self._modified_start, modified_index)
        self._original_count += 1

    def add_modified_element(self, original_index: int, modified_index: int) -> None:
        """Adds the modified element at the given position to the elements
        affected by the current change. The original index gives context
        to the change position with respect to the modified sequence."""
        self._original_start = min(self._original_start, original_index)
        self._modified_start = min(self._modified_start, modified_index)
        self._modified_count += 1

    def get_changes(self) -> list[DiffChange]:
        """Retrieves all of the changes marked by the class."""
        if self._original_count > 0 or self._modified_count > 0:
            self.mark_next_change()
        return self._changes

    def get_reverse_changes(self) -> list[DiffChange]:
        """Retrieves all of the changes marked by the class in reverse order."""
        if self._original_count > 0 or self._modified_count > 0:
            self.mark_next_change()
        self._changes.reverse()
        return self._changes


class LcsDiff:
    """An implementation of the difference algorithm described in
    "An O(ND) Difference Algorithm and its variations" by Eugene W. Myers"""

    def __init__(
        self,
        original_sequence: Sequence,
        modified_sequence: Sequence,
        continue_processing_predicate: Callable[[int, int], bool] | None = None,
    ) -> None:
        self._continue_processing_predicate = continue_processing_predicate

        self._original_sequence = original_sequence
        self._modified_sequence = modified_sequence

        (
            original_string_elements,
            original_elements_or_hash,
            original_has_strings,
        ) = self._get_elements(original_sequence)
        (
            modified_string_elements,
            modified_elements_or_hash,
            modified_has_strings,
        ) = self._get_elements(modified_sequence)

        self._has_strings: bool = original_has_strings and modified_has_strings
        self._original_string_elements: list[str] = original_string_elements
        self._original_elements_or_hash: list[int] = original_elements_or_hash
        self._modified_string_elements: list[str] = modified_string_elements
        self._modified_elements_or_hash: list[int] = modified_elements_or_hash

        self._forward_history: list[list[int]] = []
        self._reverse_history: list[list[int]] = []

    @staticmethod
    def _get_elements(
        sequence: Sequence,
    ) -> tuple[list[str], list[int], bool]:
        elements = sequence.get_elements()

        if (
            isinstance(elements, list)
            and len(elements) > 0
            and isinstance(elements[0], str)
        ):
            str_elements = cast(list[str], elements)
            hashes = [string_hash(el, 0) for el in str_elements]
            return (str_elements, hashes, True)

        if isinstance(elements, array.array):
            return ([], list(elements), False)

        # list[int]
        return ([], cast(list[int], elements), False)

    @staticmethod
    def _get_strict_element(sequence: Sequence, index: int) -> str | None:
        if hasattr(sequence, "get_strict_element") and callable(
            getattr(sequence, "get_strict_element", None)
        ):
            return sequence.get_strict_element(index)  # type: ignore[union-attr]
        return None

    def _elements_are_equal(self, original_index: int, new_index: int) -> bool:
        if (
            self._original_elements_or_hash[original_index]
            != self._modified_elements_or_hash[new_index]
        ):
            return False
        return (
            self._original_string_elements[original_index]
            == self._modified_string_elements[new_index]
            if self._has_strings
            else True
        )

    def _elements_are_strict_equal(self, original_index: int, new_index: int) -> bool:
        if not self._elements_are_equal(original_index, new_index):
            return False
        original_element = self._get_strict_element(
            self._original_sequence, original_index
        )
        modified_element = self._get_strict_element(self._modified_sequence, new_index)
        return original_element == modified_element

    def _original_elements_are_equal(self, index1: int, index2: int) -> bool:
        if (
            self._original_elements_or_hash[index1]
            != self._original_elements_or_hash[index2]
        ):
            return False
        return (
            self._original_string_elements[index1]
            == self._original_string_elements[index2]
            if self._has_strings
            else True
        )

    def _modified_elements_are_equal(self, index1: int, index2: int) -> bool:
        if (
            self._modified_elements_or_hash[index1]
            != self._modified_elements_or_hash[index2]
        ):
            return False
        return (
            self._modified_string_elements[index1]
            == self._modified_string_elements[index2]
            if self._has_strings
            else True
        )

    def compute_diff(self, pretty: bool) -> DiffResult:
        return self._compute_diff(
            0,
            len(self._original_elements_or_hash) - 1,
            0,
            len(self._modified_elements_or_hash) - 1,
            pretty,
        )

    def _compute_diff(
        self,
        original_start: int,
        original_end: int,
        modified_start: int,
        modified_end: int,
        pretty: bool,
    ) -> DiffResult:
        quit_early_arr = [False]
        changes = self._compute_diff_recursive(
            original_start,
            original_end,
            modified_start,
            modified_end,
            quit_early_arr,
        )

        if pretty:
            changes = self._prettify_changes(changes)

        return DiffResult(
            quit_early=quit_early_arr[0],
            changes=changes,
        )

    def _compute_diff_recursive(
        self,
        original_start: int,
        original_end: int,
        modified_start: int,
        modified_end: int,
        quit_early_arr: list[bool],
    ) -> list[DiffChange]:
        quit_early_arr[0] = False

        # Find the start of the differences
        while (
            original_start <= original_end
            and modified_start <= modified_end
            and self._elements_are_equal(original_start, modified_start)
        ):
            original_start += 1
            modified_start += 1

        # Find the end of the differences
        while (
            original_end >= original_start
            and modified_end >= modified_start
            and self._elements_are_equal(original_end, modified_end)
        ):
            original_end -= 1
            modified_end -= 1

        # In the special case where we either have all insertions or
        # all deletions or the sequences are identical
        if original_start > original_end or modified_start > modified_end:
            if modified_start <= modified_end:
                Debug.assert_(
                    original_start == original_end + 1,
                    "originalStart should only be one more than originalEnd",
                )
                # All insertions
                return [
                    DiffChange(
                        original_start,
                        0,
                        modified_start,
                        modified_end - modified_start + 1,
                    )
                ]
            elif original_start <= original_end:
                Debug.assert_(
                    modified_start == modified_end + 1,
                    "modifiedStart should only be one more than modifiedEnd",
                )
                # All deletions
                return [
                    DiffChange(
                        original_start,
                        original_end - original_start + 1,
                        modified_start,
                        0,
                    )
                ]
            else:
                Debug.assert_(
                    original_start == original_end + 1,
                    "originalStart should only be one more than originalEnd",
                )
                Debug.assert_(
                    modified_start == modified_end + 1,
                    "modifiedStart should only be one more than modifiedEnd",
                )
                # Identical sequences - No differences
                return []

        # This problem can be solved using the Divide-And-Conquer technique.
        mid_original_arr = [0]
        mid_modified_arr = [0]
        result = self._compute_recursion_point(
            original_start,
            original_end,
            modified_start,
            modified_end,
            mid_original_arr,
            mid_modified_arr,
            quit_early_arr,
        )

        mid_original = mid_original_arr[0]
        mid_modified = mid_modified_arr[0]

        if result is not None:
            return result
        elif not quit_early_arr[0]:
            left_changes = self._compute_diff_recursive(
                original_start,
                mid_original,
                modified_start,
                mid_modified,
                quit_early_arr,
            )
            if not quit_early_arr[0]:
                right_changes = self._compute_diff_recursive(
                    mid_original + 1,
                    original_end,
                    mid_modified + 1,
                    modified_end,
                    quit_early_arr,
                )
            else:
                right_changes = [
                    DiffChange(
                        mid_original + 1,
                        original_end - (mid_original + 1) + 1,
                        mid_modified + 1,
                        modified_end - (mid_modified + 1) + 1,
                    )
                ]

            return self._concatenate_changes(left_changes, right_changes)

        # Quit early, return everything as one change
        return [
            DiffChange(
                original_start,
                original_end - original_start + 1,
                modified_start,
                modified_end - modified_start + 1,
            )
        ]

    def _walk_trace(
        self,
        diagonal_forward_base: int,
        diagonal_forward_start: int,
        diagonal_forward_end: int,
        diagonal_forward_offset: int,
        diagonal_reverse_base: int,
        diagonal_reverse_start: int,
        diagonal_reverse_end: int,
        diagonal_reverse_offset: int,
        forward_points: list[int],
        reverse_points: list[int],
        original_index: int,
        original_end: int,
        mid_original_arr: list[int],
        modified_index: int,
        modified_end: int,
        mid_modified_arr: list[int],
        delta_is_even: bool,
        quit_early_arr: list[bool],
    ) -> list[DiffChange]:
        forward_changes: list[DiffChange] | None = None
        reverse_changes: list[DiffChange] | None = None

        # First, walk backward through the forward diagonals history
        change_helper = DiffChangeHelper()
        diagonal_min = diagonal_forward_start
        diagonal_max = diagonal_forward_end
        diagonal_relative = (
            mid_original_arr[0] - mid_modified_arr[0] - diagonal_forward_offset
        )
        last_original_index = int(Constants.MIN_SAFE_SMALL_INT)
        history_index = len(self._forward_history) - 1

        while history_index >= -1:
            diagonal = diagonal_relative + diagonal_forward_base

            if diagonal == diagonal_min or (
                diagonal < diagonal_max
                and forward_points[diagonal - 1] < forward_points[diagonal + 1]
            ):
                # Vertical line (the element is an insert)
                original_index = forward_points[diagonal + 1]
                modified_index = (
                    original_index - diagonal_relative - diagonal_forward_offset
                )
                if original_index < last_original_index:
                    change_helper.mark_next_change()
                last_original_index = original_index
                change_helper.add_modified_element(original_index + 1, modified_index)
                diagonal_relative = diagonal + 1 - diagonal_forward_base
            else:
                # Horizontal line (the element is a deletion)
                original_index = forward_points[diagonal - 1] + 1
                modified_index = (
                    original_index - diagonal_relative - diagonal_forward_offset
                )
                if original_index < last_original_index:
                    change_helper.mark_next_change()
                last_original_index = original_index - 1
                change_helper.add_original_element(original_index, modified_index + 1)
                diagonal_relative = diagonal - 1 - diagonal_forward_base

            if history_index >= 0:
                forward_points = self._forward_history[history_index]
                diagonal_forward_base = forward_points[0]
                diagonal_min = 1
                diagonal_max = len(forward_points) - 1

            history_index -= 1

        forward_changes = change_helper.get_reverse_changes()

        if quit_early_arr[0]:
            original_start_point = mid_original_arr[0] + 1
            modified_start_point = mid_modified_arr[0] + 1

            if forward_changes and len(forward_changes) > 0:
                last_forward_change = forward_changes[-1]
                original_start_point = max(
                    original_start_point,
                    last_forward_change.get_original_end(),
                )
                modified_start_point = max(
                    modified_start_point,
                    last_forward_change.get_modified_end(),
                )

            reverse_changes = [
                DiffChange(
                    original_start_point,
                    original_end - original_start_point + 1,
                    modified_start_point,
                    modified_end - modified_start_point + 1,
                )
            ]
        else:
            # Now walk backward through the reverse diagonals history
            change_helper = DiffChangeHelper()
            diagonal_min = diagonal_reverse_start
            diagonal_max = diagonal_reverse_end
            diagonal_relative = (
                mid_original_arr[0] - mid_modified_arr[0] - diagonal_reverse_offset
            )
            last_original_index = int(Constants.MAX_SAFE_SMALL_INT)
            history_index = (
                len(self._reverse_history) - 1
                if delta_is_even
                else len(self._reverse_history) - 2
            )

            while history_index >= -1:
                diagonal = diagonal_relative + diagonal_reverse_base

                if diagonal == diagonal_min or (
                    diagonal < diagonal_max
                    and reverse_points[diagonal - 1] >= reverse_points[diagonal + 1]
                ):
                    # Horizontal line (the element is a deletion)
                    original_index = reverse_points[diagonal + 1] - 1
                    modified_index = (
                        original_index - diagonal_relative - diagonal_reverse_offset
                    )
                    if original_index > last_original_index:
                        change_helper.mark_next_change()
                    last_original_index = original_index + 1
                    change_helper.add_original_element(
                        original_index + 1, modified_index + 1
                    )
                    diagonal_relative = diagonal + 1 - diagonal_reverse_base
                else:
                    # Vertical line (the element is an insertion)
                    original_index = reverse_points[diagonal - 1]
                    modified_index = (
                        original_index - diagonal_relative - diagonal_reverse_offset
                    )
                    if original_index > last_original_index:
                        change_helper.mark_next_change()
                    last_original_index = original_index
                    change_helper.add_modified_element(
                        original_index + 1, modified_index + 1
                    )
                    diagonal_relative = diagonal - 1 - diagonal_reverse_base

                if history_index >= 0:
                    reverse_points = self._reverse_history[history_index]
                    diagonal_reverse_base = reverse_points[0]
                    diagonal_min = 1
                    diagonal_max = len(reverse_points) - 1

                history_index -= 1

            reverse_changes = change_helper.get_changes()

        return self._concatenate_changes(forward_changes, reverse_changes)

    def _compute_recursion_point(
        self,
        original_start: int,
        original_end: int,
        modified_start: int,
        modified_end: int,
        mid_original_arr: list[int],
        mid_modified_arr: list[int],
        quit_early_arr: list[bool],
    ) -> list[DiffChange] | None:
        original_index = 0
        modified_index = 0
        diagonal_forward_start = 0
        diagonal_forward_end = 0
        diagonal_reverse_start = 0
        diagonal_reverse_end = 0

        # To traverse the edit graph and produce the proper LCS, our actual
        # start position is just outside the given boundary
        original_start -= 1
        modified_start -= 1

        # We set these up to make the compiler happy, but they will
        # be replaced before we return with the actual recursion point
        mid_original_arr[0] = 0
        mid_modified_arr[0] = 0

        # Clear out the history
        self._forward_history = []
        self._reverse_history = []

        # Each cell in the two arrays corresponds to a diagonal in the edit
        # graph. The integer value in the cell represents the originalIndex
        # of the furthest reaching point found so far that ends in that
        # diagonal. The modifiedIndex can be computed mathematically from
        # the originalIndex and the diagonal number.
        max_differences = (
            original_end - original_start + (modified_end - modified_start)
        )
        num_diagonals = max_differences + 1
        forward_points = [0] * num_diagonals
        reverse_points = [0] * num_diagonals
        diagonal_forward_base = modified_end - modified_start
        diagonal_reverse_base = original_end - original_start
        diagonal_forward_offset = original_start - modified_start
        diagonal_reverse_offset = original_end - modified_end
        delta = diagonal_reverse_base - diagonal_forward_base
        delta_is_even = delta % 2 == 0

        forward_points[diagonal_forward_base] = original_start
        reverse_points[diagonal_reverse_base] = original_end

        quit_early_arr[0] = False

        for num_differences in range(1, max_differences // 2 + 2):
            furthest_original_index = 0
            furthest_modified_index = 0

            # Run the algorithm in the forward direction
            diagonal_forward_start = self._clip_diagonal_bound(
                diagonal_forward_base - num_differences,
                num_differences,
                diagonal_forward_base,
                num_diagonals,
            )
            diagonal_forward_end = self._clip_diagonal_bound(
                diagonal_forward_base + num_differences,
                num_differences,
                diagonal_forward_base,
                num_diagonals,
            )

            for diagonal in range(diagonal_forward_start, diagonal_forward_end + 1, 2):
                # STEP 1: We extend the furthest reaching point in the
                # present diagonal by looking at the diagonals above and
                # below and picking the one whose point is further away
                # from the start point (original_start, modified_start)
                if diagonal == diagonal_forward_start or (
                    diagonal < diagonal_forward_end
                    and forward_points[diagonal - 1] < forward_points[diagonal + 1]
                ):
                    original_index = forward_points[diagonal + 1]
                else:
                    original_index = forward_points[diagonal - 1] + 1

                modified_index = (
                    original_index
                    - (diagonal - diagonal_forward_base)
                    - diagonal_forward_offset
                )

                # Save the current original_index so we can test for
                # false overlap in step 3
                temp_original_index = original_index

                # STEP 2: We can continue to extend the furthest reaching
                # point in the present diagonal so long as the elements
                # are equal.
                while (
                    original_index < original_end
                    and modified_index < modified_end
                    and self._elements_are_equal(original_index + 1, modified_index + 1)
                ):
                    original_index += 1
                    modified_index += 1

                forward_points[diagonal] = original_index

                if (
                    original_index + modified_index
                    > furthest_original_index + furthest_modified_index
                ):
                    furthest_original_index = original_index
                    furthest_modified_index = modified_index

                # STEP 3: If delta is odd (overlap first happens on forward
                # when delta is odd) and diagonal is in the range of reverse
                # diagonals computed for num_differences-1 (the previous
                # iteration; we haven't computed reverse diagonals for
                # num_differences yet) then check for overlap.
                if (
                    not delta_is_even
                    and abs(diagonal - diagonal_reverse_base) <= num_differences - 1
                ):
                    if original_index >= reverse_points[diagonal]:
                        mid_original_arr[0] = original_index
                        mid_modified_arr[0] = modified_index

                        if (
                            temp_original_index <= reverse_points[diagonal]
                            and _MAX_DIFFERENCES_HISTORY > 0
                            and num_differences <= _MAX_DIFFERENCES_HISTORY + 1
                        ):
                            # BINGO! We overlapped, and we have the full
                            # trace in memory!
                            return self._walk_trace(
                                diagonal_forward_base,
                                diagonal_forward_start,
                                diagonal_forward_end,
                                diagonal_forward_offset,
                                diagonal_reverse_base,
                                diagonal_reverse_start,
                                diagonal_reverse_end,
                                diagonal_reverse_offset,
                                forward_points,
                                reverse_points,
                                original_index,
                                original_end,
                                mid_original_arr,
                                modified_index,
                                modified_end,
                                mid_modified_arr,
                                delta_is_even,
                                quit_early_arr,
                            )
                        else:
                            return None

            # Check to see if we should be quitting early
            match_length_of_longest = int(
                (
                    furthest_original_index
                    - original_start
                    + (furthest_modified_index - modified_start)
                    - num_differences
                )
                / 2
            )

            if (
                self._continue_processing_predicate is not None
                and not self._continue_processing_predicate(
                    furthest_original_index, match_length_of_longest
                )
            ):
                quit_early_arr[0] = True

                mid_original_arr[0] = furthest_original_index
                mid_modified_arr[0] = furthest_modified_index

                if (
                    match_length_of_longest > 0
                    and _MAX_DIFFERENCES_HISTORY > 0
                    and num_differences <= _MAX_DIFFERENCES_HISTORY + 1
                ):
                    return self._walk_trace(
                        diagonal_forward_base,
                        diagonal_forward_start,
                        diagonal_forward_end,
                        diagonal_forward_offset,
                        diagonal_reverse_base,
                        diagonal_reverse_start,
                        diagonal_reverse_end,
                        diagonal_reverse_offset,
                        forward_points,
                        reverse_points,
                        original_index,
                        original_end,
                        mid_original_arr,
                        modified_index,
                        modified_end,
                        mid_modified_arr,
                        delta_is_even,
                        quit_early_arr,
                    )
                else:
                    original_start += 1
                    modified_start += 1

                    return [
                        DiffChange(
                            original_start,
                            original_end - original_start + 1,
                            modified_start,
                            modified_end - modified_start + 1,
                        )
                    ]

            # Run the algorithm in the reverse direction
            diagonal_reverse_start = self._clip_diagonal_bound(
                diagonal_reverse_base - num_differences,
                num_differences,
                diagonal_reverse_base,
                num_diagonals,
            )
            diagonal_reverse_end = self._clip_diagonal_bound(
                diagonal_reverse_base + num_differences,
                num_differences,
                diagonal_reverse_base,
                num_diagonals,
            )

            for diagonal in range(diagonal_reverse_start, diagonal_reverse_end + 1, 2):
                # STEP 1: Extend the furthest reaching point in the
                # present diagonal.
                if diagonal == diagonal_reverse_start or (
                    diagonal < diagonal_reverse_end
                    and reverse_points[diagonal - 1] >= reverse_points[diagonal + 1]
                ):
                    original_index = reverse_points[diagonal + 1] - 1
                else:
                    original_index = reverse_points[diagonal - 1]

                modified_index = (
                    original_index
                    - (diagonal - diagonal_reverse_base)
                    - diagonal_reverse_offset
                )

                temp_original_index = original_index

                # STEP 2: Extend as long as elements are equal.
                while (
                    original_index > original_start
                    and modified_index > modified_start
                    and self._elements_are_equal(original_index, modified_index)
                ):
                    original_index -= 1
                    modified_index -= 1

                reverse_points[diagonal] = original_index

                # STEP 4: If delta is even (overlap first happens on
                # reverse when delta is even) and diagonal is in the
                # range of forward diagonals computed for num_differences
                # then check for overlap.
                if (
                    delta_is_even
                    and abs(diagonal - diagonal_forward_base) <= num_differences
                ):
                    if original_index <= forward_points[diagonal]:
                        mid_original_arr[0] = original_index
                        mid_modified_arr[0] = modified_index

                        if (
                            temp_original_index >= forward_points[diagonal]
                            and _MAX_DIFFERENCES_HISTORY > 0
                            and num_differences <= _MAX_DIFFERENCES_HISTORY + 1
                        ):
                            return self._walk_trace(
                                diagonal_forward_base,
                                diagonal_forward_start,
                                diagonal_forward_end,
                                diagonal_forward_offset,
                                diagonal_reverse_base,
                                diagonal_reverse_start,
                                diagonal_reverse_end,
                                diagonal_reverse_offset,
                                forward_points,
                                reverse_points,
                                original_index,
                                original_end,
                                mid_original_arr,
                                modified_index,
                                modified_end,
                                mid_modified_arr,
                                delta_is_even,
                                quit_early_arr,
                            )
                        else:
                            return None

            # Save current vectors to history before the next iteration
            if num_differences <= _MAX_DIFFERENCES_HISTORY:
                temp = [diagonal_forward_base - diagonal_forward_start + 1]
                temp.extend(
                    forward_points[diagonal_forward_start : diagonal_forward_end + 1]
                )
                self._forward_history.append(temp)

                temp = [diagonal_reverse_base - diagonal_reverse_start + 1]
                temp = [diagonal_reverse_base - diagonal_reverse_start + 1]
                temp.extend(
                    reverse_points[diagonal_reverse_start : diagonal_reverse_end + 1]
                )
                self._reverse_history.append(temp)

        # If we got here, then we have the full trace in history.
        return self._walk_trace(
            diagonal_forward_base,
            diagonal_forward_start,
            diagonal_forward_end,
            diagonal_forward_offset,
            diagonal_reverse_base,
            diagonal_reverse_start,
            diagonal_reverse_end,
            diagonal_reverse_offset,
            forward_points,
            reverse_points,
            original_index,
            original_end,
            mid_original_arr,
            modified_index,
            modified_end,
            mid_modified_arr,
            delta_is_even,
            quit_early_arr,
        )

    def _prettify_changes(self, changes: list[DiffChange]) -> list[DiffChange]:
        # Shift all the changes down first
        i = 0
        while i < len(changes):
            change = changes[i]
            original_stop = (
                changes[i + 1].original_start
                if i < len(changes) - 1
                else len(self._original_elements_or_hash)
            )
            modified_stop = (
                changes[i + 1].modified_start
                if i < len(changes) - 1
                else len(self._modified_elements_or_hash)
            )
            check_original = change.original_length > 0
            check_modified = change.modified_length > 0

            while (
                change.original_start + change.original_length < original_stop
                and change.modified_start + change.modified_length < modified_stop
                and (
                    not check_original
                    or self._original_elements_are_equal(
                        change.original_start,
                        change.original_start + change.original_length,
                    )
                )
                and (
                    not check_modified
                    or self._modified_elements_are_equal(
                        change.modified_start,
                        change.modified_start + change.modified_length,
                    )
                )
            ):
                start_strict_equal = self._elements_are_strict_equal(
                    change.original_start, change.modified_start
                )
                end_strict_equal = self._elements_are_strict_equal(
                    change.original_start + change.original_length,
                    change.modified_start + change.modified_length,
                )
                if end_strict_equal and not start_strict_equal:
                    break
                change.original_start += 1
                change.modified_start += 1

            merged_change_arr: list[DiffChange] = []
            if i < len(changes) - 1 and self._changes_overlap(
                changes[i], changes[i + 1], merged_change_arr
            ):
                changes[i] = merged_change_arr[0]
                changes.pop(i + 1)
                i -= 1
            i += 1

        # Shift changes back up until we hit empty or whitespace-only lines
        i = len(changes) - 1
        while i >= 0:
            change = changes[i]

            original_stop = 0
            modified_stop = 0
            if i > 0:
                prev_change = changes[i - 1]
                original_stop = prev_change.original_start + prev_change.original_length
                modified_stop = prev_change.modified_start + prev_change.modified_length

            check_original = change.original_length > 0
            check_modified = change.modified_length > 0

            best_delta = 0
            best_score = self._boundary_score(
                change.original_start,
                change.original_length,
                change.modified_start,
                change.modified_length,
            )

            delta = 1
            while True:
                orig_start = change.original_start - delta
                mod_start = change.modified_start - delta

                if orig_start < original_stop or mod_start < modified_stop:
                    break

                if check_original and not self._original_elements_are_equal(
                    orig_start,
                    orig_start + change.original_length,
                ):
                    break

                if check_modified and not self._modified_elements_are_equal(
                    mod_start,
                    mod_start + change.modified_length,
                ):
                    break

                touching_previous_change = (
                    orig_start == original_stop and mod_start == modified_stop
                )
                score = (5 if touching_previous_change else 0) + (
                    self._boundary_score(
                        orig_start,
                        change.original_length,
                        mod_start,
                        change.modified_length,
                    )
                )

                if score > best_score:
                    best_score = score
                    best_delta = delta

                delta += 1

            change.original_start -= best_delta
            change.modified_start -= best_delta

            merged_change_arr2: list[DiffChange] = []
            if i > 0 and self._changes_overlap(
                changes[i - 1], changes[i], merged_change_arr2
            ):
                changes[i - 1] = merged_change_arr2[0]
                changes.pop(i)
                i += 1
            i -= 1

        # There could be multiple longest common substrings.
        # Give preference to the ones containing longer lines
        if self._has_strings:
            for i in range(1, len(changes)):
                a_change = changes[i - 1]
                b_change = changes[i]
                matched_length = (
                    b_change.original_start
                    - a_change.original_start
                    - a_change.original_length
                )
                a_original_start = a_change.original_start
                b_original_end = b_change.original_start + b_change.original_length
                ab_original_length = b_original_end - a_original_start
                a_modified_start = a_change.modified_start
                b_modified_end = b_change.modified_start + b_change.modified_length
                ab_modified_length = b_modified_end - a_modified_start

                if (
                    matched_length < 5
                    and ab_original_length < 20
                    and ab_modified_length < 20
                ):
                    t = self._find_better_contiguous_sequence(
                        a_original_start,
                        ab_original_length,
                        a_modified_start,
                        ab_modified_length,
                        matched_length,
                    )
                    if t is not None:
                        original_match_start, modified_match_start = t
                        if (
                            original_match_start
                            != a_change.original_start + a_change.original_length
                            or modified_match_start
                            != a_change.modified_start + a_change.modified_length
                        ):
                            a_change.original_length = (
                                original_match_start - a_change.original_start
                            )
                            a_change.modified_length = (
                                modified_match_start - a_change.modified_start
                            )
                            b_change.original_start = (
                                original_match_start + matched_length
                            )
                            b_change.modified_start = (
                                modified_match_start + matched_length
                            )
                            b_change.original_length = (
                                b_original_end - b_change.original_start
                            )
                            b_change.modified_length = (
                                b_modified_end - b_change.modified_start
                            )

        return changes

    def _find_better_contiguous_sequence(
        self,
        original_start: int,
        original_length: int,
        modified_start: int,
        modified_length: int,
        desired_length: int,
    ) -> tuple[int, int] | None:
        if original_length < desired_length or modified_length < desired_length:
            return None

        original_max = original_start + original_length - desired_length + 1
        modified_max = modified_start + modified_length - desired_length + 1
        best_score = 0
        best_original_start = 0
        best_modified_start = 0

        for i in range(original_start, original_max):
            for j in range(modified_start, modified_max):
                score = self._contiguous_sequence_score(i, j, desired_length)
                if score > 0 and score > best_score:
                    best_score = score
                    best_original_start = i
                    best_modified_start = j

        if best_score > 0:
            return (best_original_start, best_modified_start)
        return None

    def _contiguous_sequence_score(
        self,
        original_start: int,
        modified_start: int,
        length: int,
    ) -> int:
        score = 0
        for i in range(length):
            if not self._elements_are_equal(original_start + i, modified_start + i):
                return 0
            score += len(self._original_string_elements[original_start + i])
        return score

    def _original_is_boundary(self, index: int) -> bool:
        if index <= 0 or index >= len(self._original_elements_or_hash) - 1:
            return True
        return (
            self._has_strings
            and re.match(r"^\s*$", self._original_string_elements[index]) is not None
        )

    def _original_region_is_boundary(
        self, original_start: int, original_length: int
    ) -> bool:
        if self._original_is_boundary(original_start) or self._original_is_boundary(
            original_start - 1
        ):
            return True
        if original_length > 0:
            original_end = original_start + original_length
            if self._original_is_boundary(
                original_end - 1
            ) or self._original_is_boundary(original_end):
                return True
        return False

    def _modified_is_boundary(self, index: int) -> bool:
        if index <= 0 or index >= len(self._modified_elements_or_hash) - 1:
            return True
        return (
            self._has_strings
            and re.match(r"^\s*$", self._modified_string_elements[index]) is not None
        )

    def _modified_region_is_boundary(
        self, modified_start: int, modified_length: int
    ) -> bool:
        if self._modified_is_boundary(modified_start) or self._modified_is_boundary(
            modified_start - 1
        ):
            return True
        if modified_length > 0:
            modified_end = modified_start + modified_length
            if self._modified_is_boundary(
                modified_end - 1
            ) or self._modified_is_boundary(modified_end):
                return True
        return False

    def _boundary_score(
        self,
        original_start: int,
        original_length: int,
        modified_start: int,
        modified_length: int,
    ) -> int:
        original_score = (
            1
            if self._original_region_is_boundary(original_start, original_length)
            else 0
        )
        modified_score = (
            1
            if self._modified_region_is_boundary(modified_start, modified_length)
            else 0
        )
        return original_score + modified_score

    def _concatenate_changes(
        self, left: list[DiffChange], right: list[DiffChange]
    ) -> list[DiffChange]:
        if len(left) == 0 or len(right) == 0:
            return right if len(right) > 0 else left

        merged_change_arr: list[DiffChange] = []
        if self._changes_overlap(left[-1], right[0], merged_change_arr):
            result = [DiffChange(0, 0, 0, 0)] * (len(left) + len(right) - 1)
            MyArray.copy(left, 0, result, 0, len(left) - 1)
            result[len(left) - 1] = merged_change_arr[0]
            MyArray.copy(right, 1, result, len(left), len(right) - 1)
            return result
        else:
            result = [DiffChange(0, 0, 0, 0)] * (len(left) + len(right))
            MyArray.copy(left, 0, result, 0, len(left))
            MyArray.copy(right, 0, result, len(left), len(right))
            return result

    def _changes_overlap(
        self,
        left: DiffChange,
        right: DiffChange,
        merged_change_arr: list[DiffChange],
    ) -> bool:
        Debug.assert_(
            left.original_start <= right.original_start,
            "Left change is not less than or equal to right change",
        )
        Debug.assert_(
            left.modified_start <= right.modified_start,
            "Left change is not less than or equal to right change",
        )

        if (
            left.original_start + left.original_length >= right.original_start
            or left.modified_start + left.modified_length >= right.modified_start
        ):
            original_start = left.original_start
            original_length = left.original_length
            modified_start = left.modified_start
            modified_length = left.modified_length

            if left.original_start + left.original_length >= right.original_start:
                original_length = (
                    right.original_start + right.original_length - left.original_start
                )
            if left.modified_start + left.modified_length >= right.modified_start:
                modified_length = (
                    right.modified_start + right.modified_length - left.modified_start
                )

            merged_change_arr.append(
                DiffChange(
                    original_start,
                    original_length,
                    modified_start,
                    modified_length,
                )
            )
            return True
        else:
            return False

    def _clip_diagonal_bound(
        self,
        diagonal: int,
        num_differences: int,
        diagonal_base_index: int,
        num_diagonals: int,
    ) -> int:
        if diagonal >= 0 and diagonal < num_diagonals:
            return diagonal

        diagonals_below = diagonal_base_index
        diagonals_above = num_diagonals - diagonal_base_index - 1
        diff_even = num_differences % 2 == 0

        if diagonal < 0:
            lower_bound_even = diagonals_below % 2 == 0
            return 0 if diff_even == lower_bound_even else 1
        else:
            upper_bound_even = diagonals_above % 2 == 0
            return (
                num_diagonals - 1
                if diff_even == upper_bound_even
                else num_diagonals - 2
            )


def string_diff(original: str, modified: str, pretty: bool) -> list[DiffChange]:
    return (
        LcsDiff(
            StringDiffSequence(original),
            StringDiffSequence(modified),
        )
        .compute_diff(pretty)
        .changes
    )

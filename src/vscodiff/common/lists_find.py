import math
from typing import Callable


class MonotonousList[T]:
    assert_invariants = False

    _find_last_monotonous_last_idx = 0
    _prev_find_last_predicate: Callable[[T], bool] | None = None

    def __init__(self, lst: list[T]):
        self._lst = lst

    def find_last_monotonous(self, predicate: Callable[[T], bool]):
        if MonotonousList.assert_invariants:
            if self._prev_find_last_predicate:
                for item in self._lst:
                    if self._prev_find_last_predicate(item) and not predicate(item):
                        raise ValueError

            self._prev_find_last_predicate = predicate

        idx = find_last_idx_monotonous(
            self._lst, predicate, self._find_last_monotonous_last_idx
        )
        self._find_last_monotonous_last_idx = idx + 1
        return None if idx == -1 else self._lst[idx]


def find_last_monotonous[T](lst: list[T], predicate: Callable[[T], bool]):
    idx = find_last_idx_monotonous(lst, predicate)
    return None if idx == -1 else lst[idx]


def find_last_idx_monotonous[T](
    lst: list[T],
    predicate: Callable[[T], bool],
    start_idx: int = 0,
    end_idx_ex: int | None = None,
):
    if end_idx_ex is None:
        end_idx_ex = len(lst)

    i, j = start_idx, end_idx_ex
    while i < j:
        k = math.floor((i + j) / 2)
        if predicate(lst[k]):
            i = k + 1
        else:
            j = k

    return i - 1


def find_first_monotonous[T](lst: list[T], predicate: Callable[[T], bool]):
    idx = find_first_idx_monotonous_or_lst_len(lst, predicate)
    return None if idx == len(lst) else lst[idx]


def find_first_idx_monotonous_or_lst_len[T](
    lst: list[T],
    predicate: Callable[[T], bool],
    start_idx: int = 0,
    end_idx_ex: int | None = None,
):
    if end_idx_ex is None:
        end_idx_ex = len(lst)

    i, j = start_idx, end_idx_ex
    while i < j:
        k = math.floor((i + j) / 2)
        if predicate(lst[k]):
            j = k
        else:
            i = k + 1

    return i

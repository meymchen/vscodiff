from typing import Callable, Iterable


def equals[T](
    one: list[T] | None, another: list[T] | None, item_equals: Callable[[T, T], bool]
):
    if one == another:
        return True

    if one is None or another is None:
        return False

    if len(one) != len(another):
        return False

    for a, b in zip(one, another):
        if not item_equals(a, b):
            return False

    return True


def for_each_adjacent[T](lst: list[T], f: Callable[[T | None, T | None], None]):
    for i in range(len(lst)):
        f(None if i == 0 else lst[i - 1], None if i == len(lst) else lst[i])


def for_each_with_neighbors[T](
    lst: list[T], f: Callable[[T | None, T, T | None], None]
):
    for i in range(len(lst)):
        f(
            None if i == 0 else lst[i - 1],
            lst[i],
            None if i + 1 == len(lst) else lst[i + 1],
        )


def group_adjacent_by[T](items: Iterable[T], should_be_grouped: Callable[[T, T], bool]):
    current_group: list[T] | None = None
    last: T | None = None
    for item in items:
        if last is not None and should_be_grouped(last, item):
            assert current_group is not None
            current_group.append(item)
        else:
            if current_group is not None:
                yield current_group

            current_group = [item]

        last = item

    if current_group is not None:
        yield current_group

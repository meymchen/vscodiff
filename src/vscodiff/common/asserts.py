from typing import Callable


def check_adjacent_items[T](items: list[T], predicate: Callable[[T, T], bool]):
    i = 0
    while i < len(items) - 1:
        a = items[i]
        b = items[i + 1]
        if not predicate(a, b):
            return False

        i += 1

    return True

from __future__ import annotations

from typing import Callable


class SetMap[K, V]:
    def __init__(self):
        self._map: dict[K, set[V]] = {}

    def add(self, key: K, value: V) -> None:
        values = self._map.get(key)
        if values is None:
            values = set()
            self._map[key] = values

        values.add(value)

    def delete(self, key: K, value: V) -> None:
        values = self._map.get(key)
        if values is None:
            return

        values.discard(value)

        if len(values) == 0:
            del self._map[key]

    def for_each(self, key: K, fn: Callable[[V], None]) -> None:
        values = self._map.get(key)
        if values is None:
            return

        for value in values:
            fn(value)

    def get(self, key: K) -> set[V]:
        values = self._map.get(key)
        if values is None:
            return set()

        return values

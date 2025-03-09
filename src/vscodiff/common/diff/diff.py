import array
from abc import ABC, abstractmethod


class Sequence(ABC):
    @abstractmethod
    def get_elements(self) -> array.array[int] | list[int] | list[str]: ...

    @abstractmethod
    def get_strict_element(self, index: int) -> str: ...


class StringDiffSequence(Sequence):
    def __init__(self, source: str):
        super().__init__()

        self._source = source

    def get_elements(self) -> array.array[int]:
        source = self._source
        chars = array.array("i", [0] * len(source))
        for i, ch in enumerate(source):
            chars[i] = ord(ch)

        return chars

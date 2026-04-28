from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from vscodiff.common.range import Range


@dataclass
class GetValueOptions:
    preserve_bom: bool
    line_ending: str


class TextModel(ABC):
    @property
    @abstractmethod
    def uri(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_lines_content(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get_value(self, options: GetValueOptions | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_line_count(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_line_max_column(self, line_number: int) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_full_model_range(self) -> Range:
        raise NotImplementedError

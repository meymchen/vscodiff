from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vscodiff.common.range import Range


@dataclass
class SingleEditOperation:
    range: Range
    text: str | None
    force_move_markers: bool | None = None

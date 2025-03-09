from dataclasses import dataclass

from vscodiff.common.offset_range import OffsetRange


@dataclass
class SingleOffsetEdit:
    replace_range: OffsetRange
    new_text: str

    def __str__(self) -> str:
        return f"{self.replace_range} -> {self.new_text}"

    @property
    def is_empty(self):
        return len(self.new_text) == 0 and len(self.replace_range) == 0


@dataclass(init=False)
class OffsetEdit:
    edits: list[SingleOffsetEdit]

    def __init__(self, edits: list[SingleOffsetEdit]):
        last_end_ex = -1
        for edit in edits:
            if not (edit.replace_range.start >= last_end_ex):
                raise ValueError

            last_end_ex = edit.replace_range.end_exclusive

        self.edits = edits

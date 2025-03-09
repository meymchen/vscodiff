from dataclasses import dataclass


@dataclass
class DiffChange:
    original_start: int
    original_length: int
    modified_start: int
    modified_length: int

    def get_original_end(self):
        return self.original_start + self.original_length

    def get_modified_end(self):
        return self.modified_start + self.modified_length

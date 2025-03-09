import re

from vscodiff.common.char_code import CharCode


def common_prefix_length(a: str, b: str):
    length = min(len(a), len(b))
    for i in range(length):
        if ord(a[i]) != ord(b[i]):
            return i

    return length


def common_suffix_length(a: str, b: str):
    length = min(len(a), len(b))
    a_last_index = len(a) - 1
    b_last_index = len(b) - 1
    for i in range(length):
        if ord(a[a_last_index - i]) != ord(b[b_last_index - i]):
            return i

    return length


def split_lines(source: str) -> list[str]:
    return re.split("\r\n|\r|\n", source)


def first_non_whitespace_index(source: str):
    for i, ch in enumerate(source):
        ch_code = ord(ch)
        if ch_code != CharCode.SPACE and ch_code != CharCode.TAB:
            return i

    return -1


def last_non_whitespace_index(source: str, start_index: int | None = None):
    if start_index is None:
        start_index = len(source) - 1

    for i in range(start_index, -1, -1):
        ch_code = ord(source[i])
        if ch_code != CharCode.SPACE and ch_code != CharCode.TAB:
            return i

    return -1

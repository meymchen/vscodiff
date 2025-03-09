def number_hash(val: int, initial_hash_val: int):
    return ((initial_hash_val << 5) - initial_hash_val + val) | 0


def string_hash(source: str, hash_val: int):
    hash_val = number_hash(149417, hash_val)
    for s in source:
        hash_val = number_hash(ord(s), hash_val)

    return hash_val

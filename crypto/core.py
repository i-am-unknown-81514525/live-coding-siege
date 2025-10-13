from typing import Self
from .type import Handler, RndFnOut
from cryptography.hazmat.primitives.hashes import Hash, SHA3_512

def _sha3(text: str) -> str:
    hash_obj = Hash(SHA3_512())
    hash_obj.update(text.encode())
    return hash_obj.finalize().hex()


class DeterRnd[*T]:
    def __init__(self, *handlers: Handler[*T]) -> None: # type: ignore
        self.seed: str | None = None
        self.handlers = handlers
    
    def with_seed(self, seed: str) -> Self:
        if not isinstance(seed, str):
            raise TypeError("Seed must be a string")
        self.seed = seed
        return self
    
    def _collect(self, size: int) -> str:
        if self.seed is None:
            raise ValueError("Seed is not set")
        if size <= 512:
            return _sha3(self.seed)[:size]
        curr = _sha3(self.seed)[:size]
        for idx in range(size // 512):
            curr += _sha3(f"{self.seed}_{idx}")
        return curr[:size]


    def retrieve(self) -> tuple[*T]:
        total_bit = sum(map(lambda x: x[0], self.handlers))
        rnd_seed = self._collect(total_bit)
        if rnd_seed:
            rnd_int = int(rnd_seed, 16)
        else:
            rnd_int = 0
        result = []
        for bit_count, fn in self.handlers:
            rnd_int, curr = divmod(rnd_int, 2 ** bit_count)
            result.append(fn(curr))
        return tuple(result)
        

def rnd_bool() -> Handler[bool]:
    return (1, lambda x: x == 0)


def randint(low: int, high: int) -> Handler[int]:
    if low == high:
        return (0, lambda x: low)
    if low > high:
        raise ValueError("Low must be less than high")
    bit_size = (high - low).bit_length()
    lim = (high-low)
    def inner(v: int) -> int:
        base = v % (2**bit_size)
        other = v >> bit_size
        if other == 0:
            other = 2**(bit_size-1)
        k = 0
        while (base + k*other) % (2**bit_size) > lim:
            k += 1
        return ((base + k*other) % (2**bit_size)) + low
    return (bit_size*2-1, inner)

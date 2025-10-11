from collections.abc import Callable

type BitCount = int
type Handler[T] = tuple[BitCount, RndFnOut[T]]
type RndFnOut[T] = Callable[[int], T]
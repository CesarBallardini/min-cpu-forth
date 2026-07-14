"""A downward-growing stack adapter over a ``MemoryPort`` region.

This adapter is the boundary that bridges values and cells: callers push/pop plain ``int``s (the
data and return stacks hold arbitrary integers), and the adapter stores them as ``Cell``s at
``Address`` positions in the shared memory.
"""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.types import Address, Cell
from min_cpu_forth.errors import StackError
from min_cpu_forth.layout import CELL_SIZE
from min_cpu_forth.ports import StackPort

if TYPE_CHECKING:
    from min_cpu_forth.ports import MemoryPort


class DownwardStackAdapter(StackPort):
    """A stack occupying ``memory[base - size : base]``, growing toward lower addresses."""

    def __init__(self, memory: MemoryPort, base: Address, size: int) -> None:
        """Bind the stack to ``memory``'s ``[base - size, base)`` region, empty at ``base``."""
        self._memory = memory
        self._base = base
        self._floor = base - size
        self._pointer: Address = base

    def push(self, value: int) -> None:
        """Push ``value``, growing the stack toward lower addresses."""
        if self._pointer <= self._floor:
            raise StackError('stack overflow')
        self._pointer = Address(self._pointer - CELL_SIZE)
        self._memory.write(self._pointer, Cell(value))

    def pop(self) -> int:
        """Pop and return the top value."""
        if self._pointer >= self._base:
            raise StackError('stack underflow')
        value = self._memory.read(self._pointer)
        self._pointer = Address(self._pointer + CELL_SIZE)
        return value

    def peek(self) -> int:
        """Return the top value without removing it."""
        if self._pointer >= self._base:
            raise StackError('stack underflow')
        return self._memory.read(self._pointer)

    @property
    def pointer(self) -> Address:
        """The current stack-pointer address (equal to ``base`` when empty)."""
        return self._pointer

    @property
    def base(self) -> Address:
        """The empty-stack pointer address."""
        return self._base

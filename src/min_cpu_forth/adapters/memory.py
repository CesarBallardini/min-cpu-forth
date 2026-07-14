"""In-memory cell storage backing every ``MemoryPort`` consumer."""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.types import Cell
from min_cpu_forth.ports import MemoryPort

if TYPE_CHECKING:
    from min_cpu_forth.domain.types import Address


class ListMemoryAdapter(MemoryPort):
    """A flat, fixed-size cell array backed by a Python list."""

    def __init__(self, size: int) -> None:
        """Allocate ``size`` zeroed cells."""
        self._cells: list[Cell] = [Cell(0)] * size

    def read(self, address: Address) -> Cell:
        """Return the cell at ``address``."""
        return self._cells[address]

    def write(self, address: Address, value: Cell) -> None:
        """Store ``value`` into the cell at ``address``."""
        self._cells[address] = value

    @property
    def size(self) -> int:
        """The number of cells in this memory."""
        return len(self._cells)

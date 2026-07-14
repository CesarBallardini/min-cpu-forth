"""In-memory cell storage backing every ``MemoryPort`` consumer."""

from min_cpu_forth.ports import MemoryPort


class ListMemoryAdapter(MemoryPort):
    """A flat, fixed-size cell array backed by a Python list."""

    def __init__(self, size: int) -> None:
        """Allocate ``size`` zeroed cells."""
        self._cells: list[int] = [0] * size

    def read(self, address: int) -> int:
        """Return the cell at ``address``."""
        return self._cells[address]

    def write(self, address: int, value: int) -> None:
        """Store ``value`` into the cell at ``address``."""
        self._cells[address] = value

    @property
    def size(self) -> int:
        """The number of cells in this memory."""
        return len(self._cells)

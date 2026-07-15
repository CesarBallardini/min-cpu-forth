"""Length-prefixed strings ( ``[length][char...]`` ) backed by a ``MemoryPort``.

The counted string is the format shared by ``WORD``'s output buffer, the dictionary header's name
field, and the tokens ``FIND``/``NUMBER`` consume. This codec names it in one place so the same
layout isn't re-derived as cell arithmetic across the dictionary adapter and the tests.
"""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.types import Address, Cell
from min_cpu_forth.ports import CountedStringPort

if TYPE_CHECKING:
    from min_cpu_forth.ports import MemoryPort


class MemoryCountedStringAdapter(CountedStringPort):
    """Reads/writes counted strings at a given address in the shared memory."""

    def __init__(self, memory: MemoryPort) -> None:
        """Bind to the memory the counted strings live in."""
        self._memory = memory

    def read(self, address: Address) -> str:
        """Return the counted string whose length cell is at ``address``."""
        length = self._memory.read(address)
        return ''.join(chr(self._memory.read(Address(address + 1 + i))) for i in range(length))

    def write(self, address: Address, text: str) -> Address:
        """Write ``text`` as a counted string at ``address``; return the address just past it."""
        self._memory.write(address, Cell(len(text)))
        for offset, char in enumerate(text):
            self._memory.write(Address(address + 1 + offset), Cell(ord(char)))
        return Address(address + 1 + len(text))

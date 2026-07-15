"""A Forth dictionary laid out in ``cpu.mem``: link-before-name headers plus colon threads.

This adapter owns the header layout (via ``HeaderField``) that was previously smeared across the
kernel builder and its tests as raw cell arithmetic. It appends words through ``SystemVariablesPort``
(so ``DP``/``LATEST`` live in memory as real Forth variables) and walks the ``LATEST`` link chain
for ``find`` -- the search Phase 4's ``FIND`` builds on.
"""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.dtos import DictionaryHeaderDto, HeaderField
from min_cpu_forth.domain.types import Address, Cell
from min_cpu_forth.layout import DICTIONARY_BASE
from min_cpu_forth.ports import DictionaryPort

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from min_cpu_forth.domain.types import ProgramIndex
    from min_cpu_forth.ports import CountedStringPort, MemoryPort, SystemVariablesPort


class MemoryDictionaryAdapter(DictionaryPort):
    """Appends headers/threads into the shared memory and searches the link chain."""

    def __init__(
        self,
        memory: MemoryPort,
        system_variables: SystemVariablesPort,
        counted_strings: CountedStringPort,
    ) -> None:
        """Bind to the shared memory, system variables, and name codec; reset the dictionary."""
        self._memory = memory
        self._vars = system_variables
        self._names = counted_strings
        self._vars.dp = DICTIONARY_BASE
        self._vars.latest = Address(0)

    def here(self) -> Address:
        """The next free dictionary cell (``DP``)."""
        return self._vars.dp

    def append_cell(self, value: int) -> Address:
        """Append one raw cell and return the address it was written to."""
        address = self._vars.dp
        self._memory.write(address, Cell(value))
        self._vars.dp = Address(address + 1)
        return address

    def append_word(
        self,
        name: str,
        code_field: ProgramIndex,
        thread: Sequence[Address] = (),
        *,
        immediate: bool = False,
    ) -> Address:
        """Append a word (header + code field + optional colon ``thread``); return its CFA."""
        self.append_cell(self._vars.latest)  # link -> previous name field
        self.append_cell(int(immediate))
        self.append_cell(0)  # smudge: 0 = fully defined
        name_field = self.here()
        self._vars.dp = self._names.write(name_field, name)  # the name is a counted string
        cfa = self.here()
        self.append_cell(code_field)
        for item in thread:
            self.append_cell(item)
        self._vars.latest = name_field
        return cfa

    def find(self, name: str) -> DictionaryHeaderDto | None:
        """Return the header of ``name``, newest first, or ``None`` if absent."""
        for header in self.headers():
            if header.name == name:
                return header
        return None

    def headers(self) -> Iterator[DictionaryHeaderDto]:
        """Yield every installed word's header, newest first (the ``LATEST`` link chain)."""
        name_field = self._vars.latest
        while name_field != 0:
            yield self._read_header(name_field)
            name_field = Address(self._memory.read(Address(name_field - HeaderField.NAME_LENGTH)))

    def _read_header(self, name_field: Address) -> DictionaryHeaderDto:
        """Decode the header whose name field is at ``name_field``."""
        start = Address(name_field - HeaderField.NAME_LENGTH)
        name = self._names.read(name_field)
        return DictionaryHeaderDto(
            name=name,
            link=Address(self._memory.read(Address(start + HeaderField.LINK))),
            immediate=bool(self._memory.read(Address(start + HeaderField.IMMEDIATE))),
            smudge=bool(self._memory.read(Address(start + HeaderField.SMUDGE))),
            cfa=Address(name_field + 1 + len(name)),
        )

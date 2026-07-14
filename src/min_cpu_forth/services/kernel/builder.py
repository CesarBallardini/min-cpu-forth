"""Assemble the ITC kernel and lay a real dictionary into ``cpu.mem`` (Phase 1).

``KernelBuilder`` depends only on ports (`AssemblerPort` to assemble the routines, `MemoryPort` to
write the dictionary), so it stays inside the services layer. It returns a `KernelImageDto`: the
program to load into the emulator, the map of word name -> CFA, and the boot thread's address.

The types tell the Harvard-split story: ``word_cfas`` and ``dp`` are ``Address``es in ``cpu.mem``,
a code-field value is a ``ProgramIndex`` in code space, and everything written into a cell is a
``Cell`` -- so storing an address or a program index into the dictionary is a visible reinterpret.
"""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.dtos import (
    CodeWordDto,
    ColonWordDto,
    KernelImageDto,
    LiteralCellDto,
    WordReferenceDto,
)
from min_cpu_forth.domain.types import Address, Cell
from min_cpu_forth.errors import KernelError
from min_cpu_forth.layout import DICTIONARY_BASE, DP_ADDR, LATEST_ADDR
from min_cpu_forth.services.kernel.routines import CODE_WORDS, ENTER_LABEL, KERNEL_SOURCE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from min_cpu_forth.domain.dtos import ThreadItemDto, WordSpecDto
    from min_cpu_forth.ports import AssemblerPort, MemoryPort

_START_LABEL = 'START'
_EXIT_WORD = 'EXIT'


class KernelBuilder:
    """Builds the threaded-code image: assembled routines plus a dictionary written to memory."""

    def __init__(self, *, assembler: AssemblerPort, memory: MemoryPort) -> None:
        """Inject the assembler (Phase 0) and the shared cell memory the dictionary lands in."""
        self._assembler = assembler
        self._memory = memory

    def build(self, colon_words: Sequence[ColonWordDto], boot: Sequence[ThreadItemDto]) -> KernelImageDto:
        """Assemble the kernel, install every word, write the ``boot`` thread, and return the image.

        ``boot`` is the top-level thread: a ``WordReferenceDto`` invokes a word by CFA, a
        ``LiteralCellDto`` is an inline literal (it must follow a ``LIT`` reference to be pushed).
        It should end in a ``BYE`` reference -- the top level has no caller to ``EXIT`` back to.
        ``boot_thread(...)`` builds one from an ergonomic mix of word names and integers.
        """
        assembly = self._assembler.assemble(KERNEL_SOURCE)
        if assembly.labels.get(_START_LABEL) != 0:
            raise KernelError("kernel routine 'START' must assemble at program index 0")
        enter_index = assembly.labels[ENTER_LABEL]

        memory = self._memory
        word_cfas: dict[str, Address] = {}
        dp = DICTIONARY_BASE
        latest_name_field = Address(0)

        def write(value: int) -> None:
            """Append one cell to the dictionary (any address / index becomes cell data here)."""
            nonlocal dp
            memory.write(dp, Cell(value))
            dp = Address(dp + 1)

        def install_header(name: str, *, immediate: bool, code_field: int) -> Address:
            """Write a word header and its code-field cell; return the code-field address (CFA)."""
            nonlocal latest_name_field
            write(latest_name_field)  # link -> previous word's name field (0 for the first)
            write(int(immediate))  # immediate flag
            write(0)  # smudge flag: 0 = fully defined
            name_field = dp
            write(len(name))  # name length
            for char in name:
                write(ord(char))
            cfa = dp
            write(code_field)  # program index of the native routine (CODE) or ENTER (colon)
            latest_name_field = name_field
            return cfa

        def install(word: WordSpecDto) -> None:
            """Install one word, dispatching on its kind; colon words also lay their thread."""
            match word:
                case CodeWordDto(name=name, routine_label=label, immediate=immediate):
                    word_cfas[name] = install_header(name, immediate=immediate, code_field=assembly.labels[label])
                case ColonWordDto(name=name, words=words, immediate=immediate):
                    word_cfas[name] = install_header(name, immediate=immediate, code_field=enter_index)
                    for referenced in (*words, _EXIT_WORD):  # thread terminated by EXIT's CFA
                        write(self._cfa_of(referenced, word_cfas))

        for word in (*CODE_WORDS, *colon_words):
            install(word)

        boot_ip = dp
        for item in boot:
            match item:
                case WordReferenceDto(name=name):
                    write(self._cfa_of(name, word_cfas))
                case LiteralCellDto(value=value):
                    write(value)

        memory.write(DP_ADDR, Cell(dp))
        memory.write(LATEST_ADDR, Cell(latest_name_field))
        return KernelImageDto(program=assembly.program, word_cfas=dict(word_cfas), boot_ip=boot_ip)

    @staticmethod
    def _cfa_of(name: str, word_cfas: dict[str, Address]) -> Address:
        """Return the CFA of an already-installed word, or raise a clear error."""
        try:
            return word_cfas[name]
        except KeyError as exc:
            raise KernelError(f'word {name!r} is referenced before it is installed') from exc


def boot_thread(*items: str | int) -> tuple[ThreadItemDto, ...]:
    """Build a boot thread from an ergonomic mix of word names (``str``) and literals (``int``)."""
    return tuple(WordReferenceDto(item) if isinstance(item, str) else LiteralCellDto(Cell(item)) for item in items)

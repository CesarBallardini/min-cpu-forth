"""Assemble the ITC kernel and install its words into a dictionary (Phase 1-2).

``KernelBuilder`` depends only on ports (`AssemblerPort` to assemble the routines, `DictionaryPort`
to install words), so it stays inside the services layer and no longer knows the header layout --
that now lives in the dictionary adapter. It returns a `KernelImageDto`: the program to load into
the emulator, the map of word name -> CFA, and the boot thread's address.
"""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.dtos import (
    CodeWordDto,
    ColonWordDto,
    KernelImageDto,
    LiteralCellDto,
    WordReferenceDto,
)
from min_cpu_forth.domain.register import Register
from min_cpu_forth.domain.types import Cell
from min_cpu_forth.errors import KernelError
from min_cpu_forth.services.kernel.routines import CODE_WORDS, ENTER_LABEL, KERNEL_SOURCE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from min_cpu_forth.domain.dtos import ThreadItemDto, WordSpecDto
    from min_cpu_forth.domain.types import Address
    from min_cpu_forth.ports import AssemblerPort, DictionaryPort
    from min_cpu_forth.services.emulator import EmulatorService

_START_LABEL = 'START'
_EXIT_WORD = 'EXIT'


class KernelBuilder:
    """Builds the threaded-code image: assembled routines installed as words in the dictionary."""

    def __init__(self, *, assembler: AssemblerPort, dictionary: DictionaryPort) -> None:
        """Inject the assembler (Phase 0) and the dictionary the words are installed into."""
        self._assembler = assembler
        self._dictionary = dictionary

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

        dictionary = self._dictionary
        word_cfas: dict[str, Address] = {}

        def cfa_of(name: str) -> Address:
            try:
                return word_cfas[name]
            except KeyError as exc:
                raise KernelError(f'word {name!r} is referenced before it is installed') from exc

        def install(word: WordSpecDto) -> None:
            match word:
                case CodeWordDto(name=name, routine_label=label, immediate=immediate):
                    word_cfas[name] = dictionary.append_word(name, assembly.labels[label], immediate=immediate)
                case ColonWordDto(name=name, words=words, immediate=immediate):
                    thread = [cfa_of(referenced) for referenced in (*words, _EXIT_WORD)]
                    word_cfas[name] = dictionary.append_word(name, enter_index, thread, immediate=immediate)

        for word in (*CODE_WORDS, *colon_words):
            install(word)

        boot_ip = dictionary.here()
        for item in boot:
            match item:
                case WordReferenceDto(name=name):
                    dictionary.append_cell(cfa_of(name))
                case LiteralCellDto(value=value):
                    dictionary.append_cell(value)

        return KernelImageDto(program=assembly.program, word_cfas=dict(word_cfas), boot_ip=boot_ip)


def boot_thread(*items: str | int) -> tuple[ThreadItemDto, ...]:
    """Build a boot thread from an ergonomic mix of word names (``str``) and literals (``int``)."""
    return tuple(WordReferenceDto(item) if isinstance(item, str) else LiteralCellDto(Cell(item)) for item in items)


def boot(emulator: EmulatorService, image: KernelImageDto) -> None:
    """Load ``image`` into ``emulator`` and point ``IP`` at its boot thread, ready to ``run``."""
    emulator.load(image.program)
    emulator.registers.write(Register.IP, image.boot_ip)

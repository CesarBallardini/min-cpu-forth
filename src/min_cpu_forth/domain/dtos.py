"""Immutable data-transfer objects passed across the hexagon's boundaries.

These carry data between the assembler's pipeline stages and out to the emulator. They are all
frozen: a DTO is a snapshot, never a mutable handle. Per-project convention, every boundary data
structure carries the ``Dto`` suffix; ``OperandSpec`` is a static ISA descriptor, not transferred
data, so it deliberately does not.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Mapping

    from min_cpu_forth.domain.opcode import InstructionField, Opcode, OperandKind
    from min_cpu_forth.domain.types import Address, Cell, ProgramIndex


@dataclass(frozen=True, slots=True)
class InstructionDto:
    """One decoded instruction. See ``services.emulator`` for what ``a``/``b``/``offset`` mean."""

    opcode: Opcode
    a: str | None = None
    b: str | int | None = None
    offset: int | None = None


class OperandSpec(NamedTuple):
    """A single operand slot in an opcode's signature: which field it fills, and how it resolves."""

    field: InstructionField
    kind: OperandKind


@dataclass(frozen=True, slots=True)
class LineDto:
    """One parsed source line: the labels defined on it and its optional instruction.

    ``address`` is the line's start index in the emitted program; it is ``-1`` until the address
    resolver fills it in, and is excluded from equality so parsed and resolved lines compare by
    content.
    """

    lineno: int
    labels: tuple[str, ...]
    mnemonic: str | None
    operands: tuple[str, ...]
    address: int = field(default=-1, compare=False)

    def with_address(self, address: int) -> LineDto:
        """Return a copy of this line with its program ``address`` recorded."""
        return LineDto(
            lineno=self.lineno,
            labels=self.labels,
            mnemonic=self.mnemonic,
            operands=self.operands,
            address=address,
        )


@dataclass(frozen=True, slots=True)
class ResolvedProgramDto:
    """Parsed lines with their addresses assigned, plus the resolved label -> index table."""

    lines: tuple[LineDto, ...]
    labels: Mapping[str, ProgramIndex]


@dataclass(frozen=True, slots=True)
class AssemblyDto:
    """The assembler's output: a runnable instruction stream plus its label symbol table."""

    program: tuple[InstructionDto, ...]
    labels: Mapping[str, ProgramIndex]


@dataclass(frozen=True, slots=True)
class CodeWordDto:
    """A primitive word whose native routine is a label in the assembled kernel program."""

    name: str
    routine_label: str
    immediate: bool = False


@dataclass(frozen=True, slots=True)
class ColonWordDto:
    """A colon word: the ordered names of the words its thread invokes (``EXIT`` appended)."""

    name: str
    words: tuple[str, ...]
    immediate: bool = False


type WordSpecDto = CodeWordDto | ColonWordDto


@dataclass(frozen=True, slots=True)
class WordReferenceDto:
    """A thread item that invokes a word by its CFA."""

    name: str


@dataclass(frozen=True, slots=True)
class LiteralCellDto:
    """A thread item that is an inline literal cell (pushed at runtime by a preceding ``LIT``)."""

    value: Cell


type ThreadItemDto = WordReferenceDto | LiteralCellDto


class HeaderField(IntEnum):
    """Cell offsets of each field within a dictionary header, from the header's start.

    A header is ``[link][immediate][smudge][name-length][name...][code-field]``. The *name field*
    (what ``LATEST`` and links point to) is the name-length cell -- ``start + NAME_LENGTH`` -- so a
    header's link is read at ``name_field - NAME_LENGTH``. This is the single source of the layout.
    """

    LINK = 0
    IMMEDIATE = 1
    SMUDGE = 2
    NAME_LENGTH = 3
    NAME = 4


@dataclass(frozen=True, slots=True)
class DictionaryHeaderDto:
    """A word's dictionary header, decoded from ``cpu.mem``."""

    name: str
    link: Address
    immediate: bool
    smudge: bool
    cfa: Address


@dataclass(frozen=True, slots=True)
class KernelImageDto:
    """An assembled kernel plus the dictionary metadata a caller needs to boot it.

    ``program`` is loaded into the emulator; ``word_cfas`` maps each installed word's name to its
    Code Field Address (the ``cpu.mem`` cell holding its code-field value); ``boot_ip`` is the
    ``cpu.mem`` address of the boot thread's first cell, which the caller writes into ``IP`` before
    running from the kernel's ``START`` routine.
    """

    program: tuple[InstructionDto, ...]
    word_cfas: Mapping[str, Address]
    boot_ip: Address

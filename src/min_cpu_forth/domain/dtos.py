"""Immutable data-transfer objects passed across the hexagon's boundaries.

These carry data between the assembler's pipeline stages and out to the emulator. They are all
frozen: a DTO is a snapshot, never a mutable handle. Per-project convention, every boundary data
structure carries the ``Dto`` suffix; ``OperandSpec`` is a static ISA descriptor, not transferred
data, so it deliberately does not.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Mapping

    from min_cpu_forth.domain.opcode import InstructionField, Opcode, OperandKind


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
    labels: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class AssemblyDto:
    """The assembler's output: a runnable instruction stream plus its label symbol table."""

    program: tuple[InstructionDto, ...]
    labels: Mapping[str, int]

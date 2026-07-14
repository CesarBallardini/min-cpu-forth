"""ISA opcodes and the descriptors the assembler uses to place operands.

``Opcode`` is the 17-instruction ISA of ``docs/02-cpu-design.md``. ``InstructionField`` and
``OperandKind`` describe, for the assembler, which ``InstructionDto`` field a source operand
populates and how its token is resolved -- see ``domain.dtos.OperandSpec``.
"""

from enum import Enum


class Opcode(Enum):
    """The 17 opcodes of the ``docs/02-cpu-design.md`` ISA."""

    LOAD = 'LOAD'
    STORE = 'STORE'
    ADD = 'ADD'
    SUB = 'SUB'
    JMP = 'JMP'
    JZ = 'JZ'
    JS = 'JS'
    PUSH_D = 'PUSH_D'
    POP_D = 'POP_D'
    PUSH_R = 'PUSH_R'
    POP_R = 'POP_R'
    AND = 'AND'
    OR = 'OR'
    INVERT = 'INVERT'
    IN = 'IN'
    OUT = 'OUT'
    HALT = 'HALT'


class InstructionField(Enum):
    """Which ``InstructionDto`` field an assembler operand populates."""

    A = 'a'
    B = 'b'
    OFFSET = 'offset'


class OperandKind(Enum):
    """How the assembler resolves an operand token, depending on its slot.

    - ``REGISTER``: a register name, kept as a ``str``.
    - ``REGISTER_OR_IMMEDIATE``: an integer/label resolves to an immediate ``int`` (a label to its
      absolute program index); otherwise a register ``str``.
    - ``OFFSET``: an integer is a literal offset; a label resolves to a signed *relative* offset.
    """

    REGISTER = 'register'
    REGISTER_OR_IMMEDIATE = 'register_or_immediate'
    OFFSET = 'offset'

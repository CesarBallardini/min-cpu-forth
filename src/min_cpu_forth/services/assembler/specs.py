"""The ISA's per-opcode operand signatures, plus the ``SET`` pseudo-op constants.

This is the single source of truth mirrored from ``services.emulator``'s operand table: it tells
the emitter which ``InstructionDto`` field each operand fills and how the token resolves.
"""

from min_cpu_forth.domain.dtos import OperandSpec
from min_cpu_forth.domain.opcode import InstructionField, Opcode, OperandKind

_A = InstructionField.A
_B = InstructionField.B
_OFF = InstructionField.OFFSET
_REG = OperandKind.REGISTER
_REGIMM = OperandKind.REGISTER_OR_IMMEDIATE
_OFFSET = OperandKind.OFFSET

OPERAND_SPECS: dict[Opcode, tuple[OperandSpec, ...]] = {
    Opcode.LOAD: (OperandSpec(_A, _REG), OperandSpec(_B, _REG)),
    Opcode.STORE: (OperandSpec(_A, _REG), OperandSpec(_B, _REG)),
    Opcode.ADD: (OperandSpec(_A, _REG), OperandSpec(_B, _REGIMM)),
    Opcode.SUB: (OperandSpec(_A, _REG), OperandSpec(_B, _REGIMM)),
    Opcode.AND: (OperandSpec(_A, _REG), OperandSpec(_B, _REGIMM)),
    Opcode.OR: (OperandSpec(_A, _REG), OperandSpec(_B, _REGIMM)),
    Opcode.INVERT: (OperandSpec(_A, _REG),),
    Opcode.JMP: (OperandSpec(_A, _REG),),
    Opcode.JZ: (OperandSpec(_A, _REG), OperandSpec(_OFF, _OFFSET)),
    Opcode.JS: (OperandSpec(_A, _REG), OperandSpec(_OFF, _OFFSET)),
    Opcode.PUSH_D: (OperandSpec(_A, _REG),),
    Opcode.POP_D: (OperandSpec(_A, _REG),),
    Opcode.PUSH_R: (OperandSpec(_A, _REG),),
    Opcode.POP_R: (OperandSpec(_A, _REG),),
    Opcode.IN: (OperandSpec(_A, _REG),),
    Opcode.OUT: (OperandSpec(_A, _REG),),
    Opcode.HALT: (),
}

# Mnemonic text -> Opcode, for the emitter's lookup.
MNEMONICS: dict[str, Opcode] = {opcode.value: opcode for opcode in Opcode}

# Assemble-time pseudo-ops, each expanding to two real instructions (never a new opcode):
#   SET r, <const>  ->  SUB r, r ;  ADD r, <const>   (materialise a constant / label address)
#   MOV dst, src    ->  SUB dst, dst ;  ADD dst, src  (copy a register)
SET_MNEMONIC = 'SET'
MOV_MNEMONIC = 'MOV'
PSEUDO_OP_SIZES: dict[str, int] = {SET_MNEMONIC: 2, MOV_MNEMONIC: 2}

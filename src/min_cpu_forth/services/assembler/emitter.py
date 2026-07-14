"""Third assembler stage: emit the instruction stream, resolving every label reference."""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.dtos import InstructionDto
from min_cpu_forth.domain.opcode import InstructionField, Opcode, OperandKind
from min_cpu_forth.errors import AssemblerError
from min_cpu_forth.ports import InstructionEmitterPort
from min_cpu_forth.services.assembler.specs import MNEMONICS, OPERAND_SPECS, SET_MNEMONIC

if TYPE_CHECKING:
    from collections.abc import Mapping

    from min_cpu_forth.domain.dtos import LineDto, ResolvedProgramDto

_SET_OPERAND_COUNT = 2


class InstructionEmitter(InstructionEmitterPort):
    """Turns resolved lines into ``InstructionDto``s, expanding ``SET`` and resolving labels."""

    def emit(self, resolved: ResolvedProgramDto) -> tuple[InstructionDto, ...]:
        """Emit the full program (labels-only lines contribute nothing)."""
        program: list[InstructionDto] = []
        for line in resolved.lines:
            program.extend(self._emit_line(line, resolved.labels))
        return tuple(program)

    def _emit_line(self, line: LineDto, labels: Mapping[str, int]) -> list[InstructionDto]:
        """Emit the zero, one, or two instructions a single source line contributes."""
        mnemonic = line.mnemonic
        if mnemonic is None:
            return []  # a labels-only or blank line
        if mnemonic == SET_MNEMONIC:
            return self._emit_set(line, labels)
        opcode = MNEMONICS.get(mnemonic)
        if opcode is None:
            raise AssemblerError(f'line {line.lineno}: unknown mnemonic {mnemonic!r}')
        specs = OPERAND_SPECS[opcode]
        if len(line.operands) != len(specs):
            raise AssemblerError(
                f'line {line.lineno}: {mnemonic} expects {len(specs)} operand(s), got {len(line.operands)}'
            )
        a: str | None = None
        b: str | int | None = None
        offset: int | None = None
        for spec, token in zip(specs, line.operands, strict=True):
            # Dispatch on kind so each resolver returns a concrete type -- the field a REGISTER
            # fills (``a`` or ``b``) is the only thing that varies.
            match spec.kind:
                case OperandKind.REGISTER:
                    register = self._resolve_register(token, line)
                    if spec.field is InstructionField.A:
                        a = register
                    else:
                        b = register
                case OperandKind.REGISTER_OR_IMMEDIATE:
                    b = self._resolve_reg_or_immediate(token, labels, line)
                case OperandKind.OFFSET:
                    offset = self._resolve_offset(token, labels, line)
        return [InstructionDto(opcode, a=a, b=b, offset=offset)]

    def _emit_set(self, line: LineDto, labels: Mapping[str, int]) -> list[InstructionDto]:
        """Expand ``SET r, <const>`` into ``SUB r, r`` then ``ADD r, <resolved-int>``."""
        if len(line.operands) != _SET_OPERAND_COUNT:
            raise AssemblerError(
                f'line {line.lineno}: SET expects 2 operands (register, constant), got {len(line.operands)}'
            )
        register = self._resolve_register(line.operands[0], line)
        value = self._resolve_constant(line.operands[1], labels, line)
        return [
            InstructionDto(Opcode.SUB, a=register, b=register),
            InstructionDto(Opcode.ADD, a=register, b=value),
        ]

    @staticmethod
    def _resolve_register(token: str, line: LineDto) -> str:
        """Require ``token`` to be a register name (an identifier, never an integer)."""
        if _try_int(token) is not None or not token.isidentifier():
            raise AssemblerError(f'line {line.lineno}: expected a register name, got {token!r}')
        return token

    @staticmethod
    def _resolve_reg_or_immediate(token: str, labels: Mapping[str, int], line: LineDto) -> str | int:
        """Resolve an ``ADD``/``SUB``/``AND``/``OR`` ``b``: integer/label -> immediate, else register."""
        literal = _try_int(token)
        if literal is not None:
            return literal
        if token in labels:
            return labels[token]  # a label as an immediate -> its absolute index
        return InstructionEmitter._resolve_register(token, line)

    @staticmethod
    def _resolve_offset(token: str, labels: Mapping[str, int], line: LineDto) -> int:
        """Resolve a ``JZ``/``JS`` offset: integer literal, or label -> signed relative offset."""
        literal = _try_int(token)
        if literal is not None:
            return literal
        if token in labels:
            return labels[token] - (line.address + 1)
        raise AssemblerError(f'line {line.lineno}: undefined label {token!r} in branch offset')

    @staticmethod
    def _resolve_constant(token: str, labels: Mapping[str, int], line: LineDto) -> int:
        """Require ``token`` to resolve to an int: an integer literal or a label's address."""
        literal = _try_int(token)
        if literal is not None:
            return literal
        if token in labels:
            return labels[token]
        raise AssemblerError(f'line {line.lineno}: expected an integer or defined label, got {token!r}')


def _try_int(token: str) -> int | None:
    """Parse ``token`` as an int (decimal, or ``0x``/``0o``/``0b`` prefixed, sign), else ``None``."""
    try:
        return int(token, 0)
    except ValueError:
        return None

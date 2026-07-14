"""A fetch-decode-execute emulator for the ISA in `docs/02-cpu-design.md`.

`min_cpu_forth.cpu.CPU` and `min_cpu_forth.forth.ForthExecutioner` model Forth word
*semantics* directly in Python -- there's no opcode stream, no `PC`, nothing that
actually fetches and executes an instruction. This module is that missing piece: a
real `Instruction` stream, a `PC`, and a dispatch loop over the 15-opcode ISA
`docs/02-cpu-design.md` specifies. It reuses `CPU` as its *data path* only --
`cpu.mem` for `LOAD`/`STORE`, `cpu.data_stack`/`cpu.return_stack` for the stack ops --
and owns its own general-purpose register file and `PC`, entirely separate from
`CPU.ip`/`CPU.w` (which stay reserved for `ForthExecutioner`'s semantic-level model).

Per-opcode operand meaning (mirrors `docs/02-cpu-design.md`'s catalog table):

| Opcode                                  | `a`                      | `b`                         | `offset` |
|------------------------------------------|--------------------------|------------------------------|----------|
| `LOAD`                                   | dst register             | address register             | --       |
| `STORE`                                  | address register         | value register               | --       |
| `ADD` / `SUB` / `AND` / `OR`             | dst register (also LHS)  | src: register or immediate   | --       |
| `INVERT`                                 | register (in place)      | --                            | --       |
| `JMP`                                    | register holding target  | --                            | --       |
| `JZ` / `JS`                              | register to test         | --                            | offset   |
| `PUSH_D` / `POP_D` / `PUSH_R` / `POP_R`  | register                 | --                            | --       |
| `HALT`                                   | --                       | --                            | --       |

There's no text assembler here -- `docs/02-cpu-design.md` explicitly defers byte-level
encoding -- so programs are hand-built lists of `Instruction`s with raw relative
offsets, the same way the design docs' own `asm` listings work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from min_cpu_forth.cpu import CPU


class Opcode(Enum):
    """The 15 opcodes of the `docs/02-cpu-design.md` ISA."""

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
    HALT = 'HALT'


@dataclass(frozen=True, slots=True)
class Instruction:
    """One instruction. See the module docstring for what `a`/`b`/`offset` mean per opcode."""

    opcode: Opcode
    a: str | None = None
    b: str | int | None = None
    offset: int | None = None


class EmulatorError(Exception):
    """Raised when the emulator can't continue (a runaway program, or a malformed instruction)."""


class Emulator:
    """Fetches `Instruction`s from `program` and executes them against `cpu`."""

    def __init__(self, cpu: CPU, program: list[Instruction]) -> None:
        """Bind to `cpu` (the data path) and `program` (the code to run), `PC` at 0."""
        self.cpu = cpu
        self.program = program
        self.pc = 0
        self.registers: dict[str, int] = {}
        self._handlers: dict[Opcode, Callable[[Instruction], None]] = {
            Opcode.LOAD: self._exec_load,
            Opcode.STORE: self._exec_store,
            Opcode.ADD: self._exec_add,
            Opcode.SUB: self._exec_sub,
            Opcode.AND: self._exec_and,
            Opcode.OR: self._exec_or,
            Opcode.INVERT: self._exec_invert,
            Opcode.JMP: self._exec_jmp,
            Opcode.JZ: self._exec_jz,
            Opcode.JS: self._exec_js,
            Opcode.PUSH_D: self._exec_push_d,
            Opcode.POP_D: self._exec_pop_d,
            Opcode.PUSH_R: self._exec_push_r,
            Opcode.POP_R: self._exec_pop_r,
            Opcode.HALT: self._exec_halt,
        }

    def step(self) -> None:
        """Fetch the instruction at `PC`, advance `PC`, then execute it."""
        instruction = self.program[self.pc]
        self.pc += 1
        self._handlers[instruction.opcode](instruction)

    def run(self, max_steps: int = 100_000) -> None:
        """Step until `cpu.halted`. Raises `EmulatorError` past `max_steps` (runaway-loop guard)."""
        steps = 0
        while not self.cpu.halted:
            if steps >= max_steps:
                raise EmulatorError(f'exceeded {max_steps} steps without HALT')
            self.step()
            steps += 1

    def _reg(self, name: str) -> int:
        """Read `name`, defaulting undefined registers to 0."""
        return self.registers.get(name, 0)

    def _resolve(self, operand: str | int) -> int:
        """Resolve an `ADD`/`SUB`/`AND`/`OR` `b` operand: immediate if `int`, else a register."""
        return operand if isinstance(operand, int) else self._reg(operand)

    @staticmethod
    def _require_register(value: str | int | None) -> str:
        """Narrow an operand that must be a register name, or raise a clear `EmulatorError`."""
        if not isinstance(value, str):
            raise EmulatorError(f'expected a register name, got {value!r}')
        return value

    @staticmethod
    def _require_operand(value: str | int | None) -> str | int:
        """Narrow an `ADD`/`SUB`/`AND`/`OR` `b` operand, or raise a clear `EmulatorError`."""
        if value is None:
            raise EmulatorError('instruction is missing its second operand')
        return value

    @staticmethod
    def _require_offset(value: int | None) -> int:
        """Narrow a `JZ`/`JS` branch offset, or raise a clear `EmulatorError`."""
        if value is None:
            raise EmulatorError('branch instruction is missing its offset')
        return value

    def _exec_load(self, instr: Instruction) -> None:
        """`a := mem[b]` (`b` is a register holding the address)."""
        dst = self._require_register(instr.a)
        addr_reg = self._require_register(instr.b)
        self.registers[dst] = self.cpu.mem[self._reg(addr_reg)]

    def _exec_store(self, instr: Instruction) -> None:
        """`mem[a] := b` (`a` is a register holding the address, `b` a value register)."""
        addr_reg = self._require_register(instr.a)
        value_reg = self._require_register(instr.b)
        self.cpu.mem[self._reg(addr_reg)] = self._reg(value_reg)

    def _exec_add(self, instr: Instruction) -> None:
        """`a := a + b`."""
        dst = self._require_register(instr.a)
        self.registers[dst] = self._reg(dst) + self._resolve(self._require_operand(instr.b))

    def _exec_sub(self, instr: Instruction) -> None:
        """`a := a - b`."""
        dst = self._require_register(instr.a)
        self.registers[dst] = self._reg(dst) - self._resolve(self._require_operand(instr.b))

    def _exec_and(self, instr: Instruction) -> None:
        """`a := a & b`."""
        dst = self._require_register(instr.a)
        self.registers[dst] = self._reg(dst) & self._resolve(self._require_operand(instr.b))

    def _exec_or(self, instr: Instruction) -> None:
        """`a := a | b`."""
        dst = self._require_register(instr.a)
        self.registers[dst] = self._reg(dst) | self._resolve(self._require_operand(instr.b))

    def _exec_invert(self, instr: Instruction) -> None:
        """`a := ~a`."""
        dst = self._require_register(instr.a)
        self.registers[dst] = ~self._reg(dst)

    def _exec_jmp(self, instr: Instruction) -> None:
        """`PC := a`."""
        target_reg = self._require_register(instr.a)
        self.pc = self._reg(target_reg)

    def _exec_jz(self, instr: Instruction) -> None:
        """`if a == 0: PC := PC + offset` (`PC` already advanced past this instruction)."""
        tested_reg = self._require_register(instr.a)
        offset = self._require_offset(instr.offset)
        if self._reg(tested_reg) == 0:
            self.pc += offset

    def _exec_js(self, instr: Instruction) -> None:
        """`if a < 0: PC := PC + offset` (`PC` already advanced past this instruction)."""
        tested_reg = self._require_register(instr.a)
        offset = self._require_offset(instr.offset)
        if self._reg(tested_reg) < 0:
            self.pc += offset

    def _exec_push_d(self, instr: Instruction) -> None:
        """Push register `a` onto the data stack."""
        reg = self._require_register(instr.a)
        self.cpu.data_stack.push(self._reg(reg))

    def _exec_pop_d(self, instr: Instruction) -> None:
        """Pop the data stack into register `a`."""
        reg = self._require_register(instr.a)
        self.registers[reg] = self.cpu.data_stack.pop()

    def _exec_push_r(self, instr: Instruction) -> None:
        """Push register `a` onto the return stack."""
        reg = self._require_register(instr.a)
        self.cpu.return_stack.push(self._reg(reg))

    def _exec_pop_r(self, instr: Instruction) -> None:
        """Pop the return stack into register `a`."""
        reg = self._require_register(instr.a)
        self.registers[reg] = self.cpu.return_stack.pop()

    def _exec_halt(self, instr: Instruction) -> None:
        """Stop the CPU."""
        del instr
        self.cpu.halted = True

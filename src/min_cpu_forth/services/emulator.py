"""The opcode-level fetch-decode-execute machine, driven entirely through ports.

``EmulatorService`` owns a program counter and a halted flag; everything else -- registers,
memory, the two stacks, and character I/O -- it reaches only through injected port abstractions,
never a concrete adapter. Per-opcode operand meaning (mirrors ``docs/02-cpu-design.md``):

| Opcode                                  | ``a``                    | ``b``                        | ``offset`` |
|------------------------------------------|--------------------------|------------------------------|------------|
| ``LOAD``                                 | dst register             | address register             | --         |
| ``STORE``                                | address register         | value register               | --         |
| ``ADD`` / ``SUB`` / ``AND`` / ``OR``     | dst register (also LHS)  | src: register or immediate   | --         |
| ``INVERT``                               | register (in place)      | --                           | --         |
| ``JMP``                                  | register holding target  | --                           | --         |
| ``JZ`` / ``JS``                          | register to test         | --                           | offset     |
| ``PUSH_D`` / ``POP_D`` / ``PUSH_R`` / ``POP_R`` | register          | --                           | --         |
| ``IN`` / ``OUT``                         | register                 | --                           | --         |
| ``HALT``                                 | --                       | --                           | --         |
"""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.opcode import Opcode
from min_cpu_forth.errors import EmulatorError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from min_cpu_forth.domain.dtos import InstructionDto
    from min_cpu_forth.ports import (
        CharacterInputPort,
        CharacterOutputPort,
        MemoryPort,
        RegisterFilePort,
        StackPort,
    )

DEFAULT_MAX_STEPS = 100_000


class EmulatorService:
    """Fetches ``InstructionDto``s from a loaded program and executes them through its ports."""

    def __init__(
        self,
        *,
        registers: RegisterFilePort,
        memory: MemoryPort,
        data_stack: StackPort,
        return_stack: StackPort,
        char_input: CharacterInputPort,
        char_output: CharacterOutputPort,
    ) -> None:
        """Wire the emulator to its data path and I/O devices; the program is loaded separately."""
        self._registers = registers
        self._memory = memory
        self._data_stack = data_stack
        self._return_stack = return_stack
        self._char_input = char_input
        self._char_output = char_output
        self._program: Sequence[InstructionDto] = ()
        self._pc = 0
        self._halted = False
        self._handlers: dict[Opcode, Callable[[InstructionDto], None]] = {
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
            Opcode.IN: self._exec_in,
            Opcode.OUT: self._exec_out,
            Opcode.HALT: self._exec_halt,
        }

    @property
    def registers(self) -> RegisterFilePort:
        """The register file, exposed so callers can seed inputs before running."""
        return self._registers

    @property
    def pc(self) -> int:
        """The program counter (index of the next instruction to fetch)."""
        return self._pc

    @property
    def halted(self) -> bool:
        """Whether a ``HALT`` has stopped the machine."""
        return self._halted

    def load(self, program: Sequence[InstructionDto]) -> None:
        """Load ``program``, resetting the program counter and halted flag."""
        self._program = program
        self._pc = 0
        self._halted = False

    def step(self) -> None:
        """Fetch the instruction at ``pc``, advance ``pc``, then execute it."""
        instruction = self._program[self._pc]
        self._pc += 1
        self._handlers[instruction.opcode](instruction)

    def run(self, max_steps: int = DEFAULT_MAX_STEPS) -> None:
        """Step until halted. Raise ``EmulatorError`` past ``max_steps`` (runaway-loop guard)."""
        steps = 0
        while not self._halted:
            if steps >= max_steps:
                raise EmulatorError(f'exceeded {max_steps} steps without HALT')
            self.step()
            steps += 1

    @staticmethod
    def _require_register(value: str | int | None) -> str:
        """Narrow an operand that must be a register name, or raise a clear ``EmulatorError``."""
        if not isinstance(value, str):
            raise EmulatorError(f'expected a register name, got {value!r}')
        return value

    @staticmethod
    def _require_offset(value: int | None) -> int:
        """Narrow a ``JZ``/``JS`` branch offset, or raise a clear ``EmulatorError``."""
        if value is None:
            raise EmulatorError('branch instruction is missing its offset')
        return value

    def _operand_value(self, operand: str | int | None) -> int:
        """Resolve an ``ADD``/``SUB``/``AND``/``OR`` ``b``: immediate if ``int``, else a register."""
        if isinstance(operand, int):
            return operand
        return self._registers.read(self._require_register(operand))

    def _exec_load(self, instr: InstructionDto) -> None:
        """``a := mem[b]`` (``b`` is a register holding the address)."""
        dst = self._require_register(instr.a)
        addr_reg = self._require_register(instr.b)
        self._registers.write(dst, self._memory.read(self._registers.read(addr_reg)))

    def _exec_store(self, instr: InstructionDto) -> None:
        """``mem[a] := b`` (``a`` holds the address, ``b`` the value)."""
        addr_reg = self._require_register(instr.a)
        value_reg = self._require_register(instr.b)
        self._memory.write(self._registers.read(addr_reg), self._registers.read(value_reg))

    def _exec_add(self, instr: InstructionDto) -> None:
        """``a := a + b``."""
        dst = self._require_register(instr.a)
        self._registers.write(dst, self._registers.read(dst) + self._operand_value(instr.b))

    def _exec_sub(self, instr: InstructionDto) -> None:
        """``a := a - b``."""
        dst = self._require_register(instr.a)
        self._registers.write(dst, self._registers.read(dst) - self._operand_value(instr.b))

    def _exec_and(self, instr: InstructionDto) -> None:
        """``a := a & b``."""
        dst = self._require_register(instr.a)
        self._registers.write(dst, self._registers.read(dst) & self._operand_value(instr.b))

    def _exec_or(self, instr: InstructionDto) -> None:
        """``a := a | b``."""
        dst = self._require_register(instr.a)
        self._registers.write(dst, self._registers.read(dst) | self._operand_value(instr.b))

    def _exec_invert(self, instr: InstructionDto) -> None:
        """``a := ~a``."""
        dst = self._require_register(instr.a)
        self._registers.write(dst, ~self._registers.read(dst))

    def _exec_jmp(self, instr: InstructionDto) -> None:
        """``PC := a``."""
        target_reg = self._require_register(instr.a)
        self._pc = self._registers.read(target_reg)

    def _exec_jz(self, instr: InstructionDto) -> None:
        """``if a == 0: PC := PC + offset`` (``PC`` already advanced past this instruction)."""
        tested_reg = self._require_register(instr.a)
        offset = self._require_offset(instr.offset)
        if self._registers.read(tested_reg) == 0:
            self._pc += offset

    def _exec_js(self, instr: InstructionDto) -> None:
        """``if a < 0: PC := PC + offset`` (``PC`` already advanced past this instruction)."""
        tested_reg = self._require_register(instr.a)
        offset = self._require_offset(instr.offset)
        if self._registers.read(tested_reg) < 0:
            self._pc += offset

    def _exec_push_d(self, instr: InstructionDto) -> None:
        """Push register ``a`` onto the data stack."""
        self._data_stack.push(self._registers.read(self._require_register(instr.a)))

    def _exec_pop_d(self, instr: InstructionDto) -> None:
        """Pop the data stack into register ``a``."""
        self._registers.write(self._require_register(instr.a), self._data_stack.pop())

    def _exec_push_r(self, instr: InstructionDto) -> None:
        """Push register ``a`` onto the return stack."""
        self._return_stack.push(self._registers.read(self._require_register(instr.a)))

    def _exec_pop_r(self, instr: InstructionDto) -> None:
        """Pop the return stack into register ``a``."""
        self._registers.write(self._require_register(instr.a), self._return_stack.pop())

    def _exec_in(self, instr: InstructionDto) -> None:
        """Read the next input character code into register ``a``."""
        self._registers.write(self._require_register(instr.a), self._char_input.read())

    def _exec_out(self, instr: InstructionDto) -> None:
        """Write register ``a``'s value to the output device."""
        self._char_output.write(self._registers.read(self._require_register(instr.a)))

    def _exec_halt(self, instr: InstructionDto) -> None:
        """Stop the machine."""
        del instr
        self._halted = True

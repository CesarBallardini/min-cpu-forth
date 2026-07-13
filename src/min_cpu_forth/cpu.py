"""The virtual CPU: flat memory plus a data stack and a return stack.

Ported from `docs/prototypes/assembler-interpreter-4.py`, with the data stack
and return stack given non-overlapping memory regions (the prototype started
both stacks at the same address, so any real use of the return stack -- for
example `DOCOL`/`EXIT` in `min_cpu_forth.forth` -- collided with the data
stack; see `docs/design/instruction-set.md` for the intended layout).
"""

from __future__ import annotations

CELL_SIZE = 1
DICTIONARY_SIZE = 2048
DATA_STACK_SIZE = 1024
RETURN_STACK_SIZE = 1024

DATA_STACK_BASE = DICTIONARY_SIZE + DATA_STACK_SIZE
RETURN_STACK_BASE = DATA_STACK_BASE + RETURN_STACK_SIZE
MEMORY_SIZE = RETURN_STACK_BASE


class StackError(Exception):
    """Raised on stack underflow or overflow."""


class Stack:
    """A downward-growing stack backed by a shared memory list."""

    def __init__(self, memory: list[int], base: int, size: int) -> None:
        """Bind the stack to `memory[base - size : base]`, empty at `base`."""
        self.mem = memory
        self.base = base
        self.floor = base - size
        self.sp = base

    def push(self, value: int) -> None:
        """Push `value`, growing the stack toward lower addresses."""
        if self.sp <= self.floor:
            raise StackError('stack overflow')
        self.sp -= CELL_SIZE
        self.mem[self.sp] = value

    def pop(self) -> int:
        """Pop and return the top value."""
        if self.sp >= self.base:
            raise StackError('stack underflow')
        val = self.mem[self.sp]
        self.sp += CELL_SIZE
        return val

    def peek(self) -> int:
        """Return the top value without removing it."""
        if self.sp >= self.base:
            raise StackError('stack underflow')
        return self.mem[self.sp]


class CPU:
    """Flat memory, an interpreter pointer, and the two stacks ITC needs.

    Registers (`ip`, `w`) are addressed by name, matching the register-indirect
    microcode ops in `docs/design/instruction-set.md`
    (`LOAD r,[r]`, `STORE [r],r2`, `ADD r,imm`, `JMP r`, `JZ r,offset`,
    `PUSH_D`/`POP_D`, `PUSH_R`/`POP_R`, `HALT`).
    """

    def __init__(self, memory_size: int = MEMORY_SIZE) -> None:
        """Allocate memory and set up the data and return stacks at its top."""
        self.mem: list[int] = [0] * memory_size
        self.ip = 0
        self.w = 0
        self.halted = False
        self.data_stack = Stack(self.mem, DATA_STACK_BASE, DATA_STACK_SIZE)
        self.return_stack = Stack(self.mem, RETURN_STACK_BASE, RETURN_STACK_SIZE)

    def load(self, addr: int) -> None:
        """`W := mem[addr]`."""
        self.w = self.mem[addr]

    def store(self, addr: int, val: int) -> None:
        """`mem[addr] := val`."""
        self.mem[addr] = val

    def add(self, register: str, imm: int) -> None:
        """`register := register + imm`."""
        setattr(self, register, getattr(self, register) + imm)

    def jmp(self, addr: int) -> None:
        """`IP := addr`."""
        self.ip = addr

    def jz(self, register: str, offset: int) -> None:
        """`if register == 0 then IP := IP + offset`."""
        if getattr(self, register) == 0:
            self.ip += offset

    def push_d(self, register: str) -> None:
        """Push `register`'s value onto the data stack."""
        self.data_stack.push(getattr(self, register))

    def pop_d(self, register: str) -> None:
        """Pop the data stack into `register`."""
        setattr(self, register, self.data_stack.pop())

    def push_r(self, register: str) -> None:
        """Push `register`'s value onto the return stack."""
        self.return_stack.push(getattr(self, register))

    def pop_r(self, register: str) -> None:
        """Pop the return stack into `register`."""
        setattr(self, register, self.return_stack.pop())

    def halt(self) -> None:
        """Stop the CPU."""
        self.halted = True

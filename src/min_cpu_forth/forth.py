"""A minimal ITC Forth inner interpreter built on `min_cpu_forth.cpu.CPU`.

Ported from `docs/prototypes/assembler-interpreter-4.py`. Words are Python
callables keyed by name rather than compiled threads of code-field addresses,
so this models Forth *semantics* (stack effects, `DOCOL`/`EXIT`, colon
definitions) without implementing the byte-level `NEXT` fetch-decode loop
described in `docs/design/instruction-set.md`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from min_cpu_forth.cpu import CPU

BinaryOp = Callable[[int, int], int]


class ForthExecutioner:
    """Dictionary of Forth primitives plus support for colon definitions."""

    def __init__(self, cpu: CPU) -> None:
        """Bind to `cpu` and install the minimal word set."""
        self.cpu = cpu
        self.dict: dict[str, Callable[..., None]] = {}
        self.colon_defs: dict[str, list[str]] = {}
        self.build_minimal_dictionary()

    def add_colon_def(self, name: str, code: list[str]) -> None:
        """Define `name` as the sequence of words in `code` (a colon definition)."""
        self.colon_defs[name] = code
        self.dict[name] = lambda name=name: self._execute_colon(name)

    def _execute_colon(self, name: str) -> None:
        """Run each word of the colon definition `name` in order."""
        code = self.colon_defs[name]
        for word in code:
            if word not in self.dict:
                raise ValueError(f'Unknown word: {word}')
            self.dict[word]()

    def build_minimal_dictionary(self) -> None:
        """Install the stack, arithmetic, memory, and control primitives."""
        # --- Stack ops ---
        self.dict['DUP'] = lambda: self.cpu.data_stack.push(self.cpu.data_stack.peek())
        self.dict['DROP'] = self._drop
        self.dict['SWAP'] = self._swap
        self.dict['OVER'] = self._over
        self.dict['ROT'] = self._rot
        self.dict['-ROT'] = self._neg_rot
        self.dict['NIP'] = self._nip
        self.dict['TUCK'] = self._tuck

        # --- Arithmetic ---
        self.dict['+'] = lambda: self._binop(lambda a, b: a + b)
        self.dict['-'] = lambda: self._binop(lambda a, b: a - b)
        self.dict['*'] = lambda: self._binop(lambda a, b: a * b)
        self.dict['/'] = lambda: self._binop(lambda a, b: a // b)
        self.dict['MOD'] = lambda: self._binop(lambda a, b: a % b)
        self.dict['NEGATE'] = lambda: self.cpu.data_stack.push(-self.cpu.data_stack.pop())
        self.dict['ABS'] = lambda: self.cpu.data_stack.push(abs(self.cpu.data_stack.pop()))
        self.dict['1+'] = lambda: self.cpu.data_stack.push(self.cpu.data_stack.pop() + 1)
        self.dict['1-'] = lambda: self.cpu.data_stack.push(self.cpu.data_stack.pop() - 1)

        # --- Memory ops ---
        self.dict['@'] = lambda: self.cpu.data_stack.push(self.cpu.mem[self.cpu.data_stack.pop()])
        self.dict['!'] = self._store
        # byte access could be implemented similarly (C@, C!)

        # --- Return stack ---
        self.dict['>R'] = lambda: self.cpu.return_stack.push(self.cpu.data_stack.pop())
        self.dict['R>'] = lambda: self.cpu.data_stack.push(self.cpu.return_stack.pop())
        self.dict['R@'] = lambda: self.cpu.data_stack.push(self.cpu.return_stack.peek())

        # --- Comparisons / Logic ---
        self.dict['='] = lambda: self._binop(lambda a, b: int(a == b))
        self.dict['<>'] = lambda: self._binop(lambda a, b: int(a != b))
        self.dict['<'] = lambda: self._binop(lambda a, b: int(a < b))
        self.dict['>'] = lambda: self._binop(lambda a, b: int(a > b))
        self.dict['0='] = lambda: self.cpu.data_stack.push(int(self.cpu.data_stack.pop() == 0))
        self.dict['0<'] = lambda: self.cpu.data_stack.push(int(self.cpu.data_stack.pop() < 0))
        self.dict['AND'] = lambda: self._binop(lambda a, b: a & b)
        self.dict['OR'] = lambda: self._binop(lambda a, b: a | b)
        self.dict['INVERT'] = lambda: self.cpu.data_stack.push(~self.cpu.data_stack.pop())

        # --- Forth control primitives ---
        self.dict['LIT'] = lambda n: self.cpu.data_stack.push(n)
        self.dict['DOCOL'] = lambda addr: self._docol(addr)
        self.dict['EXIT'] = self._exit

        # --- Control structures are implemented as colon definitions ---
        self.dict['IF'] = lambda: None
        self.dict['ELSE'] = lambda: None
        self.dict['THEN'] = lambda: None
        self.dict['BEGIN'] = lambda: None
        self.dict['UNTIL'] = lambda: None
        self.dict['WHILE'] = lambda: None
        self.dict['REPEAT'] = lambda: None
        self.dict['DO'] = lambda: None
        self.dict['LOOP'] = lambda: None
        self.dict['+LOOP'] = lambda: None
        self.dict['BYE'] = self.cpu.halt

    # ----------------------
    # Helper methods
    # ----------------------
    def _binop(self, func: BinaryOp) -> None:
        """Pop two values (b then a), push `func(a, b)`."""
        b = self.cpu.data_stack.pop()
        a = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(func(a, b))

    def _swap(self) -> None:
        """`( a b -- b a )`."""
        a = self.cpu.data_stack.pop()
        b = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(a)
        self.cpu.data_stack.push(b)

    def _drop(self) -> None:
        """`( x -- )`."""
        self.cpu.data_stack.pop()

    def _over(self) -> None:
        """`( a b -- a b a )`."""
        b = self.cpu.data_stack.pop()
        a = self.cpu.data_stack.peek()
        self.cpu.data_stack.push(b)
        self.cpu.data_stack.push(a)

    def _rot(self) -> None:
        """`( a b c -- b c a )`."""
        c = self.cpu.data_stack.pop()
        b = self.cpu.data_stack.pop()
        a = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(b)
        self.cpu.data_stack.push(c)
        self.cpu.data_stack.push(a)

    def _neg_rot(self) -> None:
        """`( a b c -- c a b )`."""
        c = self.cpu.data_stack.pop()
        b = self.cpu.data_stack.pop()
        a = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(c)
        self.cpu.data_stack.push(a)
        self.cpu.data_stack.push(b)

    def _nip(self) -> None:
        """`( a b -- b )`."""
        a = self.cpu.data_stack.pop()
        self.cpu.data_stack.pop()
        self.cpu.data_stack.push(a)

    def _tuck(self) -> None:
        """`( a b -- b a b )`."""
        a = self.cpu.data_stack.pop()
        b = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(a)
        self.cpu.data_stack.push(b)
        self.cpu.data_stack.push(a)

    def _store(self) -> None:
        """`( x addr -- )`: store `x` at `addr` (addr is on top of the stack)."""
        addr = self.cpu.data_stack.pop()
        value = self.cpu.data_stack.pop()
        self.cpu.mem[addr] = value

    def _docol(self, addr: int) -> None:
        """Enter the colon definition at `addr`: save `IP`, then jump into it."""
        self.cpu.push_r('ip')
        self.cpu.ip = addr

    def _exit(self) -> None:
        """Return from a colon definition: restore `IP` from the return stack."""
        self.cpu.pop_r('ip')


def build_standard_colon_defs(vm: ForthExecutioner) -> None:
    """Install placeholder colon definitions for structured control words."""
    # IF ... ELSE ... THEN
    # Compiles down to: 0BRANCH (skip if false), optional BRANCH (skip ELSE)
    vm.add_colon_def('IF_THEN', ['0BRANCH'])  # user would compile literals and 0BRANCH
    vm.add_colon_def('IF_ELSE_THEN', ['0BRANCH', 'BRANCH'])  # simplified

    # BEGIN ... UNTIL
    vm.add_colon_def('BEGIN_UNTIL', ['BEGIN', 'UNTIL'])  # simplified placeholder

    # WHILE ... REPEAT
    vm.add_colon_def('WHILE_REPEAT', ['WHILE', 'REPEAT'])

    # DO ... LOOP
    vm.add_colon_def('DO_LOOP', ['DO', 'LOOP'])
    vm.add_colon_def('DO_PLUS_LOOP', ['DO', '+LOOP'])

    # EXIT
    vm.add_colon_def(';', ['EXIT'])

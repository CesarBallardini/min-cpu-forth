"""A minimal ITC Forth inner interpreter, modelling word *semantics* over the shared data path.

Ported from ``docs/prototypes/assembler-interpreter-4.py``. Words are Python callables keyed by
name rather than compiled threads of code-field addresses, so this models Forth semantics (stack
effects, ``DOCOL``/``EXIT``, colon definitions) without the byte-level ``NEXT`` fetch-decode loop
that ``services.emulator`` implements. It reaches memory, the stacks, and the interpreter pointer
only through injected ports -- never a concrete adapter.
"""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.register import Register
from min_cpu_forth.domain.types import Address, Cell
from min_cpu_forth.errors import UnknownWordError

if TYPE_CHECKING:
    from collections.abc import Callable

    from min_cpu_forth.ports import MemoryPort, RegisterFilePort, StackPort

type BinaryOp = Callable[[int, int], int]
type Word = Callable[..., None]


def _noop() -> None:
    """Do nothing -- a placeholder for control-structure words not yet compiled."""


class ForthService:
    """A dictionary of Forth primitives plus support for colon definitions."""

    def __init__(
        self,
        *,
        data_stack: StackPort,
        return_stack: StackPort,
        memory: MemoryPort,
        registers: RegisterFilePort,
    ) -> None:
        """Wire to the shared data path and install the minimal word set."""
        self._data_stack = data_stack
        self._return_stack = return_stack
        self._memory = memory
        self._registers = registers
        self._halted = False
        self.dictionary: dict[str, Word] = {}
        self.colon_defs: dict[str, list[str]] = {}
        self.build_minimal_dictionary()

    @property
    def halted(self) -> bool:
        """Whether ``BYE`` has stopped the interpreter."""
        return self._halted

    def add_colon_def(self, name: str, code: list[str]) -> None:
        """Define ``name`` as the sequence of words in ``code`` (a colon definition)."""
        self.colon_defs[name] = code
        self.dictionary[name] = lambda captured=name: self._execute_colon(captured)

    def _execute_colon(self, name: str) -> None:
        """Run each word of the colon definition ``name`` in order."""
        for word in self.colon_defs[name]:
            if word not in self.dictionary:
                raise UnknownWordError(f'Unknown word: {word}')
            self.dictionary[word]()

    def build_minimal_dictionary(self) -> None:  # noqa: PLR0915 -- one flat table of primitives
        """Install the stack, arithmetic, memory, and control primitives."""
        # --- Stack ops ---
        self.dictionary['DUP'] = lambda: self._data_stack.push(self._data_stack.peek())
        self.dictionary['DROP'] = self._drop
        self.dictionary['SWAP'] = self._swap
        self.dictionary['OVER'] = self._over
        self.dictionary['ROT'] = self._rot
        self.dictionary['-ROT'] = self._neg_rot
        self.dictionary['NIP'] = self._nip
        self.dictionary['TUCK'] = self._tuck

        # --- Arithmetic ---
        self.dictionary['+'] = lambda: self._binop(lambda a, b: a + b)
        self.dictionary['-'] = lambda: self._binop(lambda a, b: a - b)
        self.dictionary['*'] = lambda: self._binop(lambda a, b: a * b)
        self.dictionary['/'] = lambda: self._binop(lambda a, b: a // b)
        self.dictionary['MOD'] = lambda: self._binop(lambda a, b: a % b)
        self.dictionary['NEGATE'] = lambda: self._data_stack.push(-self._data_stack.pop())
        self.dictionary['ABS'] = lambda: self._data_stack.push(abs(self._data_stack.pop()))
        self.dictionary['1+'] = lambda: self._data_stack.push(self._data_stack.pop() + 1)
        self.dictionary['1-'] = lambda: self._data_stack.push(self._data_stack.pop() - 1)

        # --- Memory ops ---
        self.dictionary['@'] = lambda: self._data_stack.push(self._memory.read(Address(self._data_stack.pop())))
        self.dictionary['!'] = self._store

        # --- Return stack ---
        self.dictionary['>R'] = lambda: self._return_stack.push(self._data_stack.pop())
        self.dictionary['R>'] = lambda: self._data_stack.push(self._return_stack.pop())
        self.dictionary['R@'] = lambda: self._data_stack.push(self._return_stack.peek())

        # --- Comparisons / logic ---
        self.dictionary['='] = lambda: self._binop(lambda a, b: int(a == b))
        self.dictionary['<>'] = lambda: self._binop(lambda a, b: int(a != b))
        self.dictionary['<'] = lambda: self._binop(lambda a, b: int(a < b))
        self.dictionary['>'] = lambda: self._binop(lambda a, b: int(a > b))
        self.dictionary['0='] = lambda: self._data_stack.push(int(self._data_stack.pop() == 0))
        self.dictionary['0<'] = lambda: self._data_stack.push(int(self._data_stack.pop() < 0))
        self.dictionary['AND'] = lambda: self._binop(lambda a, b: a & b)
        self.dictionary['OR'] = lambda: self._binop(lambda a, b: a | b)
        self.dictionary['INVERT'] = lambda: self._data_stack.push(~self._data_stack.pop())

        # --- Forth control primitives ---
        self.dictionary['LIT'] = self._data_stack.push
        self.dictionary['DOCOL'] = self._docol
        self.dictionary['EXIT'] = self._exit
        self.dictionary['BYE'] = self._bye

        # --- Control structures: no-op placeholders, compiled as colon definitions later
        #     (Phase 6 of docs/03-assembler-plan.md replaces these stubs). ---
        for structure_word in ('IF', 'ELSE', 'THEN', 'BEGIN', 'UNTIL', 'WHILE', 'REPEAT', 'DO', 'LOOP', '+LOOP'):
            self.dictionary[structure_word] = _noop

    def _binop(self, func: BinaryOp) -> None:
        """Pop two values (``b`` then ``a``), push ``func(a, b)``."""
        b = self._data_stack.pop()
        a = self._data_stack.pop()
        self._data_stack.push(func(a, b))

    def _swap(self) -> None:
        """``( a b -- b a )``."""
        a = self._data_stack.pop()
        b = self._data_stack.pop()
        self._data_stack.push(a)
        self._data_stack.push(b)

    def _drop(self) -> None:
        """``( x -- )``."""
        self._data_stack.pop()

    def _over(self) -> None:
        """``( a b -- a b a )``."""
        b = self._data_stack.pop()
        a = self._data_stack.peek()
        self._data_stack.push(b)
        self._data_stack.push(a)

    def _rot(self) -> None:
        """``( a b c -- b c a )``."""
        c = self._data_stack.pop()
        b = self._data_stack.pop()
        a = self._data_stack.pop()
        self._data_stack.push(b)
        self._data_stack.push(c)
        self._data_stack.push(a)

    def _neg_rot(self) -> None:
        """``( a b c -- c a b )``."""
        c = self._data_stack.pop()
        b = self._data_stack.pop()
        a = self._data_stack.pop()
        self._data_stack.push(c)
        self._data_stack.push(a)
        self._data_stack.push(b)

    def _nip(self) -> None:
        """``( a b -- b )``."""
        a = self._data_stack.pop()
        self._data_stack.pop()
        self._data_stack.push(a)

    def _tuck(self) -> None:
        """``( a b -- b a b )``."""
        a = self._data_stack.pop()
        b = self._data_stack.pop()
        self._data_stack.push(a)
        self._data_stack.push(b)
        self._data_stack.push(a)

    def _store(self) -> None:
        """``( x addr -- )``: store ``x`` at ``addr`` (address on top of the stack)."""
        addr = self._data_stack.pop()
        value = self._data_stack.pop()
        self._memory.write(Address(addr), Cell(value))

    def _docol(self, addr: int) -> None:
        """Enter the colon definition at ``addr``: save ``IP``, then jump into it."""
        self._return_stack.push(self._registers.read(Register.IP))
        self._registers.write(Register.IP, addr)

    def _exit(self) -> None:
        """Return from a colon definition: restore ``IP`` from the return stack."""
        self._registers.write(Register.IP, self._return_stack.pop())

    def _bye(self) -> None:
        """Stop the interpreter."""
        self._halted = True


def build_standard_colon_defs(service: ForthService) -> None:
    """Install placeholder colon definitions for structured control words."""
    service.add_colon_def('IF_THEN', ['0BRANCH'])
    service.add_colon_def('IF_ELSE_THEN', ['0BRANCH', 'BRANCH'])
    service.add_colon_def('BEGIN_UNTIL', ['BEGIN', 'UNTIL'])
    service.add_colon_def('WHILE_REPEAT', ['WHILE', 'REPEAT'])
    service.add_colon_def('DO_LOOP', ['DO', 'LOOP'])
    service.add_colon_def('DO_PLUS_LOOP', ['DO', '+LOOP'])
    service.add_colon_def(';', ['EXIT'])

"""Port protocols: the hexagon's boundary abstractions.

Adapters in ``min_cpu_forth.adapters`` implement these; services in ``min_cpu_forth.services``
depend only on these abstractions and are wired to concrete adapters by the dependency-injection
container. Nothing here imports an adapter -- the dependency arrow points inward, toward the ports.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from min_cpu_forth.domain.dtos import (
        AssemblyDto,
        InstructionDto,
        LineDto,
        ResolvedProgramDto,
    )
    from min_cpu_forth.domain.types import Address, Cell


@runtime_checkable
class MemoryPort(Protocol):
    """Random-access cell storage shared by the stacks, ``LOAD``/``STORE``, and the dictionary."""

    def read(self, address: Address) -> Cell:
        """Return the cell at ``address``."""
        ...

    def write(self, address: Address, value: Cell) -> None:
        """Store ``value`` into the cell at ``address``."""
        ...

    @property
    def size(self) -> int:
        """The number of cells in this memory."""
        ...


@runtime_checkable
class StackPort(Protocol):
    """A last-in-first-out stack of cells (the data stack or the return stack)."""

    def push(self, value: int) -> None:
        """Push ``value`` onto the stack."""
        ...

    def pop(self) -> int:
        """Pop and return the top value."""
        ...

    def peek(self) -> int:
        """Return the top value without removing it."""
        ...

    @property
    def pointer(self) -> Address:
        """The current stack-pointer address (equal to ``base`` when empty)."""
        ...

    @property
    def base(self) -> Address:
        """The empty-stack pointer address; the stack grows toward lower addresses."""
        ...


@runtime_checkable
class RegisterFilePort(Protocol):
    """A name-addressed set of integer registers; unset registers read as zero."""

    def read(self, name: str) -> int:
        """Return register ``name`` (``0`` if never written)."""
        ...

    def write(self, name: str, value: int) -> None:
        """Set register ``name`` to ``value``."""
        ...


@runtime_checkable
class CharacterInputPort(Protocol):
    """A source of input characters for the ``IN`` opcode / ``KEY``."""

    def read(self) -> int:
        """Return the next input character code, raising ``InputExhaustedError`` if none remain."""
        ...


@runtime_checkable
class CharacterOutputPort(Protocol):
    """A sink for output characters from the ``OUT`` opcode / ``EMIT``."""

    def write(self, value: int) -> None:
        """Append the character code ``value`` to the output."""
        ...


@runtime_checkable
class SourcePort(Protocol):
    """A provider of assembler source text (a string, a file, stdin, ...)."""

    def read(self) -> str:
        """Return the full assembler source."""
        ...


@runtime_checkable
class LineParserPort(Protocol):
    """First assembler stage: source text -> parsed lines (addresses not yet assigned)."""

    def parse(self, source: str) -> tuple[LineDto, ...]:
        """Parse ``source`` into one ``LineDto`` per source line."""
        ...


@runtime_checkable
class AddressResolverPort(Protocol):
    """Second assembler stage: assign each label its program index across the whole unit."""

    def resolve(self, lines: tuple[LineDto, ...]) -> ResolvedProgramDto:
        """Return ``lines`` with addresses filled in, plus the label -> index table."""
        ...


@runtime_checkable
class InstructionEmitterPort(Protocol):
    """Third assembler stage: resolved lines -> the runnable instruction stream."""

    def emit(self, resolved: ResolvedProgramDto) -> tuple[InstructionDto, ...]:
        """Emit ``InstructionDto``s, resolving every label reference to a number."""
        ...


@runtime_checkable
class AssemblerPort(Protocol):
    """The assembler use case: source text -> a runnable ``AssemblyDto``."""

    def assemble(self, source: str) -> AssemblyDto:
        """Assemble ``source`` into a program plus its symbol table."""
        ...

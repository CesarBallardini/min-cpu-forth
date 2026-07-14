"""The assembler use case: orchestrates parse -> resolve -> emit through injected ports."""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.dtos import AssemblyDto
from min_cpu_forth.ports import AssemblerPort

if TYPE_CHECKING:
    from min_cpu_forth.ports import (
        AddressResolverPort,
        InstructionEmitterPort,
        LineParserPort,
    )


class TextAssembler(AssemblerPort):
    """Wires the three assembler stages together; depends only on their port abstractions."""

    def __init__(
        self,
        *,
        parser: LineParserPort,
        resolver: AddressResolverPort,
        emitter: InstructionEmitterPort,
    ) -> None:
        """Inject the parser, address resolver, and instruction emitter."""
        self._parser = parser
        self._resolver = resolver
        self._emitter = emitter

    def assemble(self, source: str) -> AssemblyDto:
        """Assemble ``source`` into a program plus its label symbol table."""
        resolved = self._resolver.resolve(self._parser.parse(source))
        program = self._emitter.emit(resolved)
        return AssemblyDto(program=program, labels=resolved.labels)

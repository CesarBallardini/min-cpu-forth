"""Second assembler stage: assign every label its program index across the whole unit."""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.dtos import ResolvedProgramDto
from min_cpu_forth.domain.types import ProgramIndex
from min_cpu_forth.errors import AssemblerError
from min_cpu_forth.ports import AddressResolverPort
from min_cpu_forth.services.assembler.specs import PSEUDO_OP_SIZES

if TYPE_CHECKING:
    from min_cpu_forth.domain.dtos import LineDto


class LabelAddressResolver(AddressResolverPort):
    """Walks the parsed lines once, recording each label's start index and detecting collisions."""

    def resolve(self, lines: tuple[LineDto, ...]) -> ResolvedProgramDto:
        """Return ``lines`` with addresses filled in, plus the label -> index table."""
        labels: dict[str, ProgramIndex] = {}
        placed: list[LineDto] = []
        address = ProgramIndex(0)
        for line in lines:
            for name in line.labels:
                if name in labels:
                    raise AssemblerError(f'line {line.lineno}: duplicate label {name!r}')
                labels[name] = address
            placed.append(line.with_address(address))
            address = ProgramIndex(address + self._size(line))
        return ResolvedProgramDto(lines=tuple(placed), labels=labels)

    @staticmethod
    def _size(line: LineDto) -> int:
        """How many instructions ``line`` emits (0 if labels-only, 2 for a ``SET``/``MOV``, else 1)."""
        if line.mnemonic is None:
            return 0
        return PSEUDO_OP_SIZES.get(line.mnemonic, 1)

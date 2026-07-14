"""First assembler stage: tokenize source text into ``LineDto``s (addresses unassigned)."""

import re

from min_cpu_forth.domain.dtos import LineDto
from min_cpu_forth.errors import AssemblerError
from min_cpu_forth.ports import LineParserPort

_LABEL_PREFIX = re.compile(r'\s*([A-Za-z_]\w*):')


class LineParser(LineParserPort):
    """Splits source into lines, peeling off ``label:`` definitions and ``;`` comments."""

    def parse(self, source: str) -> tuple[LineDto, ...]:
        """Parse ``source`` into one ``LineDto`` per source line."""
        return tuple(self._parse_line(lineno, raw) for lineno, raw in enumerate(source.splitlines(), start=1))

    @staticmethod
    def _parse_line(lineno: int, raw: str) -> LineDto:
        """Peel comment and leading labels, then split the mnemonic from its operand list."""
        work = raw.split(';', 1)[0]
        labels: list[str] = []
        while (match := _LABEL_PREFIX.match(work)) is not None:
            labels.append(match.group(1))
            work = work[match.end() :]
        work = work.strip()
        if not work:
            return LineDto(lineno=lineno, labels=tuple(labels), mnemonic=None, operands=())
        mnemonic, remainder = _split_mnemonic(work)
        operands = tuple(part.strip() for part in remainder.split(',') if part.strip())
        return LineDto(lineno=lineno, labels=tuple(labels), mnemonic=mnemonic, operands=operands)


def _split_mnemonic(text: str) -> tuple[str, str]:
    """Split ``text`` into its first whitespace-delimited token (the mnemonic) and the rest."""
    parts = text.split(None, 1)
    if not parts[0].replace('_', '').isalnum():
        raise AssemblerError(f'malformed mnemonic {parts[0]!r}')
    return parts[0], parts[1] if len(parts) > 1 else ''

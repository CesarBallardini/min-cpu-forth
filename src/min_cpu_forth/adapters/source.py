"""A ``SourcePort`` that yields a fixed in-memory string."""

from min_cpu_forth.ports import SourcePort


class StringSourceAdapter(SourcePort):
    """Serves assembler source held directly in memory as a string."""

    def __init__(self, source: str) -> None:
        """Hold ``source`` to hand back on ``read``."""
        self._source = source

    def read(self) -> str:
        """Return the held assembler source."""
        return self._source

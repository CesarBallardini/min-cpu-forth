"""A dict-backed register file; unset registers read as zero."""

from min_cpu_forth.ports import RegisterFilePort


class DictRegisterFileAdapter(RegisterFilePort):
    """Name-addressed integer registers, defaulting to ``0`` when never written."""

    def __init__(self) -> None:
        """Start with every register unset (reading any yields ``0``)."""
        self._registers: dict[str, int] = {}

    def read(self, name: str) -> int:
        """Return register ``name`` (``0`` if never written)."""
        return self._registers.get(name, 0)

    def write(self, name: str, value: int) -> None:
        """Set register ``name`` to ``value``."""
        self._registers[name] = value

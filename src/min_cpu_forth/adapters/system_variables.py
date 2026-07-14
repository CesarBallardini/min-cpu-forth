"""Forth system variables stored as fixed cells in ``cpu.mem``."""

from typing import TYPE_CHECKING

from min_cpu_forth.domain.types import Address, Cell
from min_cpu_forth.layout import DP_ADDR, LATEST_ADDR
from min_cpu_forth.ports import SystemVariablesPort

if TYPE_CHECKING:
    from min_cpu_forth.ports import MemoryPort


class MemorySystemVariablesAdapter(SystemVariablesPort):
    """``DP`` and ``LATEST`` backed by their fixed cells in the shared memory."""

    def __init__(self, memory: MemoryPort) -> None:
        """Bind to the memory whose ``DP_ADDR``/``LATEST_ADDR`` cells hold the variables."""
        self._memory = memory

    @property
    def dp(self) -> Address:
        """The dictionary pointer (HERE)."""
        return Address(self._memory.read(DP_ADDR))

    @dp.setter
    def dp(self, value: Address) -> None:
        self._memory.write(DP_ADDR, Cell(value))

    @property
    def latest(self) -> Address:
        """The name field of the most recently defined word."""
        return Address(self._memory.read(LATEST_ADDR))

    @latest.setter
    def latest(self, value: Address) -> None:
        self._memory.write(LATEST_ADDR, Cell(value))

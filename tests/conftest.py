"""Shared fixtures for the whole test suite."""

import pytest

from min_cpu_forth.cpu import CPU
from min_cpu_forth.forth import ForthExecutioner


@pytest.fixture
def cpu() -> CPU:
    """A fresh CPU, with empty data and return stacks, for each test."""
    return CPU()


@pytest.fixture
def forth(cpu: CPU) -> ForthExecutioner:
    """A ForthExecutioner with the minimal dictionary installed on `cpu`."""
    return ForthExecutioner(cpu)

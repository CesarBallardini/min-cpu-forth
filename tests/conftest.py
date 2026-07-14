"""Shared fixtures for the whole test suite.

Each test gets a fresh ``MachineContainer``; because its providers are singletons scoped to the
container instance, every fixture that requests ``machine`` shares one clean data path (memory
and both stacks), exactly as the wired-together services do at runtime.
"""

from typing import TYPE_CHECKING

import pytest

from min_cpu_forth.containers import AssemblerContainer, MachineContainer

if TYPE_CHECKING:
    from min_cpu_forth.adapters.io import (
        BufferCharacterOutputAdapter,
        QueueCharacterInputAdapter,
    )
    from min_cpu_forth.ports import AssemblerPort, MemoryPort, RegisterFilePort, StackPort
    from min_cpu_forth.services.emulator import EmulatorService
    from min_cpu_forth.services.forth import ForthService


@pytest.fixture
def machine() -> MachineContainer:
    """A fresh, fully wired machine container for one test."""
    return MachineContainer()


@pytest.fixture
def memory(machine: MachineContainer) -> MemoryPort:
    """The shared cell memory."""
    return machine.memory()


@pytest.fixture
def data_stack(machine: MachineContainer) -> StackPort:
    """The shared data stack."""
    return machine.data_stack()


@pytest.fixture
def return_stack(machine: MachineContainer) -> StackPort:
    """The shared return stack."""
    return machine.return_stack()


@pytest.fixture
def emulator(machine: MachineContainer) -> EmulatorService:
    """The opcode emulator, sharing the data path above."""
    return machine.emulator()


@pytest.fixture
def registers(machine: MachineContainer) -> RegisterFilePort:
    """The emulator's register file (the same instance ``emulator`` uses)."""
    return machine.emulator_registers()


@pytest.fixture
def char_input(machine: MachineContainer) -> QueueCharacterInputAdapter:
    """The emulator's input device."""
    return machine.char_input()


@pytest.fixture
def char_output(machine: MachineContainer) -> BufferCharacterOutputAdapter:
    """The emulator's output device."""
    return machine.char_output()


@pytest.fixture
def forth(machine: MachineContainer) -> ForthService:
    """The Forth interpreter, sharing the data path above."""
    return machine.forth()


@pytest.fixture
def forth_registers(machine: MachineContainer) -> RegisterFilePort:
    """The Forth interpreter's register file (holding ``IP``)."""
    return machine.forth_registers()


@pytest.fixture
def assembler() -> AssemblerPort:
    """A text assembler wired from its three stages."""
    return AssemblerContainer().assembler()

"""Shared fixtures for the whole test suite.

Each test gets a fresh ``MachineContainer``; because its providers are singletons scoped to the
container instance, every fixture that requests ``machine`` shares one clean data path (memory
and both stacks), exactly as the wired-together services do at runtime.
"""

from typing import TYPE_CHECKING, NamedTuple, Protocol

import pytest

from min_cpu_forth.containers import AssemblerContainer, KernelContainer, MachineContainer
from min_cpu_forth.domain.types import Address
from min_cpu_forth.services.kernel.builder import boot as boot_image
from min_cpu_forth.services.kernel.builder import boot_thread

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from min_cpu_forth.adapters.io import (
        BufferCharacterOutputAdapter,
        QueueCharacterInputAdapter,
    )
    from min_cpu_forth.domain.dtos import ColonWordDto, KernelImageDto
    from min_cpu_forth.ports import AssemblerPort, MemoryPort, RegisterFilePort, StackPort
    from min_cpu_forth.services.emulator import EmulatorService
    from min_cpu_forth.services.forth import ForthService


class MachineState(NamedTuple):
    """The observable Forth-machine state after a kernel run -- what a test asserts against.

    ``data_stack`` is the result; ``return_stack`` should be balanced after a well-formed run;
    ``registers`` exposes the reserved registers (IP/W/XT/NEXTREG); ``memory`` is the data space;
    ``output`` is the character buffer EMIT wrote to; ``halted`` confirms a clean BYE/HALT.
    """

    data_stack: StackPort
    return_stack: StackPort
    registers: RegisterFilePort
    memory: MemoryPort
    output: BufferCharacterOutputAdapter
    halted: bool


class RunKernel(Protocol):
    """Builds a kernel from a boot thread, runs it, and returns the final ``MachineState``.

    ``feed`` seeds the input device; ``colon_words`` are installed before the boot thread;
    ``string_at`` writes a counted string at an address; ``after_build`` is a hook that runs once
    the image is built (before ``run``) for tests that must poke memory mid-flight.
    """

    def __call__(
        self,
        *,
        boot: Sequence[str | int],
        feed: str = ...,
        colon_words: Sequence[ColonWordDto] = ...,
        string_at: tuple[int, str] | None = ...,
        after_build: Callable[[KernelContainer, KernelImageDto], None] | None = ...,
    ) -> MachineState: ...


@pytest.fixture
def run_kernel(kernel: KernelContainer) -> RunKernel:
    """A callable that builds + runs a kernel and captures its final ``MachineState``."""

    def _run(
        *,
        boot: Sequence[str | int],
        feed: str = '',
        colon_words: Sequence[ColonWordDto] = (),
        string_at: tuple[int, str] | None = None,
        after_build: Callable[[KernelContainer, KernelImageDto], None] | None = None,
    ) -> MachineState:
        machine = kernel.machine()
        emulator = machine.emulator()
        image = kernel.kernel_builder().build(colon_words=list(colon_words), boot=boot_thread(*boot))
        if string_at is not None:
            address, text = string_at
            kernel.counted_strings().write(Address(address), text)
        if after_build is not None:
            after_build(kernel, image)
        if feed:
            machine.char_input().feed([ord(char) for char in feed])
        boot_image(emulator, image)
        emulator.run()
        return MachineState(
            data_stack=machine.data_stack(),
            return_stack=machine.return_stack(),
            registers=emulator.registers,
            memory=machine.memory(),
            output=machine.char_output(),
            halted=emulator.halted,
        )

    return _run


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


@pytest.fixture
def kernel() -> KernelContainer:
    """A fresh kernel container (its own machine + assembler) per test."""
    return KernelContainer()

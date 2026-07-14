"""Unit tests for the dependency-injection containers: state sharing and isolation."""

import pytest

from min_cpu_forth import layout
from min_cpu_forth.containers import KernelContainer, MachineContainer
from min_cpu_forth.domain.dtos import InstructionDto
from min_cpu_forth.domain.opcode import Opcode
from min_cpu_forth.domain.types import Address, Cell
from min_cpu_forth.services.kernel.builder import boot_thread


@pytest.mark.unit
def test_a_machine_shares_one_data_path_across_its_services() -> None:
    """The emulator and the Forth interpreter from one container use the same data stack."""
    machine = MachineContainer()
    forth = machine.forth()
    emulator = machine.emulator()

    forth.dictionary['LIT'](7)  # ForthService pushes onto the shared data stack
    emulator.load([InstructionDto(Opcode.POP_D, a='X'), InstructionDto(Opcode.HALT)])
    emulator.run()

    assert emulator.registers.read('X') == 7  # noqa: PLR2004 -- popped what Forth pushed


@pytest.mark.unit
def test_two_machine_containers_are_independent() -> None:
    """Providers are singletons per container instance, so separate machines never share memory."""
    first = MachineContainer()
    second = MachineContainer()

    first.memory().write(Address(100), Cell(42))

    assert second.memory().read(Address(100)) == 0


@pytest.mark.unit
def test_kernel_container_shares_memory_between_builder_and_emulator() -> None:
    """The builder writes the dictionary into the very memory the machine exposes (same singleton)."""
    kernel = KernelContainer()
    builder = kernel.kernel_builder()
    memory = kernel.machine().memory()

    builder.build(colon_words=[], boot=boot_thread('BYE'))

    # LIT is installed first; its name-length cell is visible through the machine's memory.
    assert memory.read(Address(layout.DICTIONARY_BASE + 3)) == len('LIT')


@pytest.mark.unit
def test_two_kernel_containers_are_independent() -> None:
    kernel_a = KernelContainer()
    kernel_b = KernelContainer()

    kernel_a.machine().memory().write(Address(200), Cell(99))

    assert kernel_b.machine().memory().read(Address(200)) == 0

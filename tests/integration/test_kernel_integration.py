"""Integration: build and run an ITC kernel with a colon definition, with no test doubles.

Spans the real AssemblerContainer -> KernelBuilder -> dictionary in MemoryPort -> EmulatorService,
threading Phase 2 primitives inside a colon word.
"""

import pytest

from min_cpu_forth.containers import KernelContainer
from min_cpu_forth.domain.dtos import ColonWordDto
from min_cpu_forth.services.kernel.builder import boot, boot_thread


@pytest.mark.integration
def test_kernel_runs_a_colon_composed_of_primitives() -> None:
    kernel = KernelContainer()
    machine = kernel.machine()
    emulator = machine.emulator()

    # DEC-DOUBLE = 1- DUP + : ( n -- (n-1)*2 )
    image = kernel.kernel_builder().build(
        colon_words=[ColonWordDto(name='DEC-DOUBLE', words=('1-', 'DUP', '+'))],
        boot=boot_thread('LIT', 5, 'DEC-DOUBLE', 'BYE'),
    )
    boot(emulator, image)
    emulator.run()

    assert machine.data_stack().pop() == 8  # (5 - 1) = 4, then DUP + = 8

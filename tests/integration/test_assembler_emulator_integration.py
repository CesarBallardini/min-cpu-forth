"""Integration: assemble source text and run it end-to-end with no test doubles.

Spans the real `AssemblerContainer` -> `EmulatorService` -> `MemoryPort` -> `StackPort`, exercising
STORE/LOAD round-tripping through memory and the ``SET`` pseudo-op materialising addresses.
"""

import pytest

from min_cpu_forth.containers import AssemblerContainer, MachineContainer
from min_cpu_forth.domain.types import Address


@pytest.mark.integration
def test_assemble_store_and_load_through_the_full_stack() -> None:
    source = """
            SET    ADDR, 500     ; a scratch data address
            SET    VAL, 42
            STORE  ADDR, VAL     ; mem[500] := 42
            LOAD   OUT, ADDR     ; read it back
            PUSH_D OUT
            HALT
    """
    program = AssemblerContainer().assembler().assemble(source).program

    machine = MachineContainer()
    emulator = machine.emulator()
    emulator.load(program)
    emulator.run()

    assert machine.memory().read(Address(500)) == 42
    assert machine.data_stack().pop() == 42

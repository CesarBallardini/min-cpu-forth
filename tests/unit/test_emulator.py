"""Unit tests for the opcode-level emulator service (``docs/02-cpu-design.md``'s ISA)."""

from typing import TYPE_CHECKING

import pytest

from min_cpu_forth.domain.dtos import InstructionDto
from min_cpu_forth.domain.opcode import Opcode
from min_cpu_forth.errors import EmulatorError, InputExhaustedError

if TYPE_CHECKING:
    from min_cpu_forth.adapters.io import (
        BufferCharacterOutputAdapter,
        QueueCharacterInputAdapter,
    )
    from min_cpu_forth.ports import MemoryPort, RegisterFilePort, StackPort
    from min_cpu_forth.services.emulator import EmulatorService


@pytest.mark.unit
def test_load_reads_memory_through_a_register(
    emulator: EmulatorService, memory: MemoryPort, registers: RegisterFilePort
) -> None:
    memory.write(100, 42)
    registers.write('ADDR', 100)
    emulator.load([InstructionDto(Opcode.LOAD, a='X', b='ADDR')])

    emulator.step()

    assert emulator.registers.read('X') == 42


@pytest.mark.unit
def test_store_writes_memory_through_a_register(
    emulator: EmulatorService, memory: MemoryPort, registers: RegisterFilePort
) -> None:
    registers.write('ADDR', 100)
    registers.write('X', 42)
    emulator.load([InstructionDto(Opcode.STORE, a='ADDR', b='X')])

    emulator.step()

    assert memory.read(100) == 42


@pytest.mark.unit
def test_add_with_immediate_operand(emulator: EmulatorService, registers: RegisterFilePort) -> None:
    registers.write('X', 10)
    emulator.load([InstructionDto(Opcode.ADD, a='X', b=5)])

    emulator.step()

    assert emulator.registers.read('X') == 15


@pytest.mark.unit
def test_add_with_register_operand(emulator: EmulatorService, registers: RegisterFilePort) -> None:
    registers.write('X', 10)
    registers.write('Y', 5)
    emulator.load([InstructionDto(Opcode.ADD, a='X', b='Y')])

    emulator.step()

    assert emulator.registers.read('X') == 15


@pytest.mark.unit
def test_sub_self_zeroes_a_register(emulator: EmulatorService, registers: RegisterFilePort) -> None:
    """The ``SUB r, r`` idiom ``docs/02-cpu-design.md`` relies on for MOV/NEGATE/comparisons."""
    registers.write('X', 99)
    emulator.load([InstructionDto(Opcode.SUB, a='X', b='X')])

    emulator.step()

    assert emulator.registers.read('X') == 0


@pytest.mark.unit
def test_and_or_invert(emulator: EmulatorService, registers: RegisterFilePort) -> None:
    registers.write('X', 0b1010)
    registers.write('Y', 0b0100)
    registers.write('Z', 0)
    emulator.load(
        [
            InstructionDto(Opcode.AND, a='X', b=0b1100),
            InstructionDto(Opcode.OR, a='Y', b=0b0011),
            InstructionDto(Opcode.INVERT, a='Z'),
        ]
    )

    emulator.step()
    emulator.step()
    emulator.step()

    assert emulator.registers.read('X') == 0b1000
    assert emulator.registers.read('Y') == 0b0111
    assert emulator.registers.read('Z') == ~0


@pytest.mark.unit
def test_jmp_sets_pc_absolutely(emulator: EmulatorService, registers: RegisterFilePort) -> None:
    registers.write('TARGET', 7)
    emulator.load([InstructionDto(Opcode.JMP, a='TARGET')])

    emulator.step()

    assert emulator.pc == 7


@pytest.mark.unit
def test_jz_branches_when_register_is_zero(emulator: EmulatorService, registers: RegisterFilePort) -> None:
    registers.write('X', 0)
    emulator.load([InstructionDto(Opcode.JZ, a='X', offset=10)])

    emulator.step()

    assert emulator.pc == 1 + 10


@pytest.mark.unit
def test_jz_does_not_branch_when_register_is_nonzero(emulator: EmulatorService, registers: RegisterFilePort) -> None:
    registers.write('X', 1)
    emulator.load([InstructionDto(Opcode.JZ, a='X', offset=10)])

    emulator.step()

    assert emulator.pc == 1


@pytest.mark.unit
def test_js_branches_when_register_is_negative(emulator: EmulatorService, registers: RegisterFilePort) -> None:
    registers.write('X', -1)
    emulator.load([InstructionDto(Opcode.JS, a='X', offset=10)])

    emulator.step()

    assert emulator.pc == 1 + 10


@pytest.mark.unit
def test_push_d_and_pop_d_round_trip_through_the_real_data_stack(
    emulator: EmulatorService, registers: RegisterFilePort, data_stack: StackPort
) -> None:
    registers.write('X', 42)
    emulator.load([InstructionDto(Opcode.PUSH_D, a='X'), InstructionDto(Opcode.POP_D, a='Y')])

    emulator.step()
    assert data_stack.peek() == 42

    emulator.step()
    assert emulator.registers.read('Y') == 42


@pytest.mark.unit
def test_push_r_and_pop_r_round_trip_through_the_real_return_stack(
    emulator: EmulatorService, registers: RegisterFilePort, return_stack: StackPort
) -> None:
    registers.write('X', 42)
    emulator.load([InstructionDto(Opcode.PUSH_R, a='X'), InstructionDto(Opcode.POP_R, a='Y')])

    emulator.step()
    assert return_stack.peek() == 42

    emulator.step()
    assert emulator.registers.read('Y') == 42


@pytest.mark.unit
def test_halt_stops_run(emulator: EmulatorService) -> None:
    emulator.load([InstructionDto(Opcode.HALT)])

    emulator.run()

    assert emulator.halted is True


@pytest.mark.unit
def test_in_reads_from_the_input_device(emulator: EmulatorService, char_input: QueueCharacterInputAdapter) -> None:
    char_input.feed([ord('A')])
    emulator.load([InstructionDto(Opcode.IN, a='X')])

    emulator.step()

    assert emulator.registers.read('X') == ord('A')


@pytest.mark.unit
def test_in_raises_when_input_is_exhausted(emulator: EmulatorService) -> None:
    emulator.load([InstructionDto(Opcode.IN, a='X')])

    with pytest.raises(InputExhaustedError):
        emulator.step()


@pytest.mark.unit
def test_out_writes_to_the_output_device(
    emulator: EmulatorService,
    registers: RegisterFilePort,
    char_output: BufferCharacterOutputAdapter,
) -> None:
    registers.write('X', ord('!'))
    emulator.load([InstructionDto(Opcode.OUT, a='X')])

    emulator.step()

    assert list(char_output.buffer) == [ord('!')]


@pytest.mark.unit
def test_dup_via_repeated_push_pop(emulator: EmulatorService, data_stack: StackPort) -> None:
    """``DUP`` exactly as written in ``docs/02-cpu-design.md``."""
    data_stack.push(7)
    emulator.load(
        [
            InstructionDto(Opcode.POP_D, a='X'),
            InstructionDto(Opcode.PUSH_D, a='X'),
            InstructionDto(Opcode.PUSH_D, a='X'),
            InstructionDto(Opcode.HALT),
        ]
    )

    emulator.run()

    assert data_stack.pop() == 7
    assert data_stack.pop() == 7


@pytest.mark.unit
def test_multiply_via_repeated_addition(
    emulator: EmulatorService, registers: RegisterFilePort, data_stack: StackPort
) -> None:
    """``*`` exactly as written in ``docs/02-cpu-design.md``'s "Synthesizing everything else"."""
    registers.write('LOOP_ADDR', 3)
    data_stack.push(6)
    data_stack.push(7)
    emulator.load(
        [
            InstructionDto(Opcode.POP_D, a='X'),  # 0: X := b (counter)
            InstructionDto(Opcode.POP_D, a='Y'),  # 1: Y := a
            InstructionDto(Opcode.SUB, a='ACC', b='ACC'),  # 2: ACC := 0
            InstructionDto(Opcode.JZ, a='X', offset=3),  # 3: LOOP -- if X==0 jump to index 7
            InstructionDto(Opcode.ADD, a='ACC', b='Y'),  # 4
            InstructionDto(Opcode.SUB, a='X', b=1),  # 5
            InstructionDto(Opcode.JMP, a='LOOP_ADDR'),  # 6: jump back to index 3
            InstructionDto(Opcode.PUSH_D, a='ACC'),  # 7: DONE
            InstructionDto(Opcode.HALT),  # 8
        ]
    )

    emulator.run()

    assert data_stack.pop() == 42  # noqa: PLR2004 -- 6 * 7


@pytest.mark.unit
def test_run_raises_when_max_steps_exceeded(emulator: EmulatorService, registers: RegisterFilePort) -> None:
    """A genuine infinite loop: ``JMP`` back to itself, no reachable ``HALT``."""
    registers.write('SELF', 0)
    emulator.load([InstructionDto(Opcode.JMP, a='SELF')])

    with pytest.raises(EmulatorError):
        emulator.run(max_steps=10)

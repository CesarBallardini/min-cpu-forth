"""Unit tests for the opcode-level emulator (`docs/02-cpu-design.md`'s ISA)."""

from typing import TYPE_CHECKING

import pytest

from min_cpu_forth.emulator import Emulator, EmulatorError, Instruction, Opcode

if TYPE_CHECKING:
    from min_cpu_forth.cpu import CPU


@pytest.mark.unit
def test_load_reads_memory_through_a_register(cpu: CPU) -> None:
    cpu.mem[100] = 42
    emulator = Emulator(cpu, [Instruction(Opcode.LOAD, a='X', b='ADDR')])
    emulator.registers['ADDR'] = 100

    emulator.step()

    assert emulator.registers['X'] == 42


@pytest.mark.unit
def test_store_writes_memory_through_a_register(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.STORE, a='ADDR', b='X')])
    emulator.registers['ADDR'] = 100
    emulator.registers['X'] = 42

    emulator.step()

    assert cpu.mem[100] == 42


@pytest.mark.unit
def test_add_with_immediate_operand(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.ADD, a='X', b=5)])
    emulator.registers['X'] = 10

    emulator.step()

    assert emulator.registers['X'] == 15


@pytest.mark.unit
def test_add_with_register_operand(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.ADD, a='X', b='Y')])
    emulator.registers['X'] = 10
    emulator.registers['Y'] = 5

    emulator.step()

    assert emulator.registers['X'] == 15


@pytest.mark.unit
def test_sub_with_register_operand(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.SUB, a='X', b='Y')])
    emulator.registers['X'] = 10
    emulator.registers['Y'] = 3

    emulator.step()

    assert emulator.registers['X'] == 7


@pytest.mark.unit
def test_sub_self_zeroes_a_register(cpu: CPU) -> None:
    """The `SUB r, r` idiom `docs/02-cpu-design.md` relies on for MOV/NEGATE/comparisons."""
    emulator = Emulator(cpu, [Instruction(Opcode.SUB, a='X', b='X')])
    emulator.registers['X'] = 99

    emulator.step()

    assert emulator.registers['X'] == 0


@pytest.mark.unit
def test_and_or_invert(cpu: CPU) -> None:
    emulator = Emulator(
        cpu,
        [
            Instruction(Opcode.AND, a='X', b=0b1100),
            Instruction(Opcode.OR, a='Y', b=0b0011),
            Instruction(Opcode.INVERT, a='Z'),
        ],
    )
    emulator.registers['X'] = 0b1010
    emulator.registers['Y'] = 0b0100
    emulator.registers['Z'] = 0

    emulator.step()
    emulator.step()
    emulator.step()

    assert emulator.registers['X'] == 0b1000
    assert emulator.registers['Y'] == 0b0111
    assert emulator.registers['Z'] == ~0


@pytest.mark.unit
def test_jmp_sets_pc_absolutely(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.JMP, a='TARGET')])
    emulator.registers['TARGET'] = 7

    emulator.step()

    assert emulator.pc == 7


@pytest.mark.unit
def test_jz_branches_when_register_is_zero(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.JZ, a='X', offset=10)])
    emulator.registers['X'] = 0

    emulator.step()

    assert emulator.pc == 1 + 10


@pytest.mark.unit
def test_jz_does_not_branch_when_register_is_nonzero(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.JZ, a='X', offset=10)])
    emulator.registers['X'] = 1

    emulator.step()

    assert emulator.pc == 1


@pytest.mark.unit
def test_js_branches_when_register_is_negative(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.JS, a='X', offset=10)])
    emulator.registers['X'] = -1

    emulator.step()

    assert emulator.pc == 1 + 10


@pytest.mark.unit
def test_js_does_not_branch_when_register_is_nonnegative(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.JS, a='X', offset=10)])
    emulator.registers['X'] = 0

    emulator.step()

    assert emulator.pc == 1


@pytest.mark.unit
def test_push_d_and_pop_d_round_trip_through_the_real_data_stack(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.PUSH_D, a='X'), Instruction(Opcode.POP_D, a='Y')])
    emulator.registers['X'] = 42

    emulator.step()
    assert cpu.data_stack.peek() == 42

    emulator.step()
    assert emulator.registers['Y'] == 42


@pytest.mark.unit
def test_push_r_and_pop_r_round_trip_through_the_real_return_stack(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.PUSH_R, a='X'), Instruction(Opcode.POP_R, a='Y')])
    emulator.registers['X'] = 42

    emulator.step()
    assert cpu.return_stack.peek() == 42

    emulator.step()
    assert emulator.registers['Y'] == 42


@pytest.mark.unit
def test_halt_stops_run(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.HALT)])

    emulator.run()

    assert cpu.halted is True


@pytest.mark.unit
def test_in_reads_from_the_input_queue(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.IN, a='X')])
    emulator.input_queue.append(ord('A'))

    emulator.step()

    assert emulator.registers['X'] == ord('A')


@pytest.mark.unit
def test_in_raises_when_input_queue_is_empty(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.IN, a='X')])

    with pytest.raises(EmulatorError):
        emulator.step()


@pytest.mark.unit
def test_out_appends_to_output(cpu: CPU) -> None:
    emulator = Emulator(cpu, [Instruction(Opcode.OUT, a='X')])
    emulator.registers['X'] = ord('!')

    emulator.step()

    assert emulator.output == [ord('!')]


@pytest.mark.unit
def test_dup_via_repeated_push_pop(cpu: CPU) -> None:
    """`DUP` exactly as written in minimal-itc-forth-primitives-1.md / docs/02-cpu-design.md."""
    program = [
        Instruction(Opcode.POP_D, a='X'),
        Instruction(Opcode.PUSH_D, a='X'),
        Instruction(Opcode.PUSH_D, a='X'),
        Instruction(Opcode.HALT),
    ]
    cpu.data_stack.push(7)

    Emulator(cpu, program).run()

    assert cpu.data_stack.pop() == 7
    assert cpu.data_stack.pop() == 7


@pytest.mark.unit
def test_multiply_via_repeated_addition(cpu: CPU) -> None:
    """`*` exactly as written in docs/02-cpu-design.md's "Synthesizing everything else"."""
    program = [
        Instruction(Opcode.POP_D, a='X'),  # 0: X := b (counter)
        Instruction(Opcode.POP_D, a='Y'),  # 1: Y := a
        Instruction(Opcode.SUB, a='ACC', b='ACC'),  # 2: ACC := 0
        Instruction(Opcode.JZ, a='X', offset=3),  # 3: LOOP -- if X==0, jump to index 7
        Instruction(Opcode.ADD, a='ACC', b='Y'),  # 4
        Instruction(Opcode.SUB, a='X', b=1),  # 5
        Instruction(Opcode.JMP, a='LOOP_ADDR'),  # 6: jump back to index 3
        Instruction(Opcode.PUSH_D, a='ACC'),  # 7: DONE
        Instruction(Opcode.HALT),  # 8
    ]
    emulator = Emulator(cpu, program)
    emulator.registers['LOOP_ADDR'] = 3
    cpu.data_stack.push(6)
    cpu.data_stack.push(7)

    emulator.run()

    assert cpu.data_stack.pop() == 42


@pytest.mark.unit
def test_run_raises_when_max_steps_exceeded(cpu: CPU) -> None:
    """A genuine infinite loop: `JMP` back to itself, no reachable `HALT`."""
    emulator = Emulator(cpu, [Instruction(Opcode.JMP, a='SELF')])
    emulator.registers['SELF'] = 0

    with pytest.raises(EmulatorError):
        emulator.run(max_steps=10)

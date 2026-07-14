"""Unit tests for the Phase 0 text assembler pipeline (``docs/03-assembler-plan.md``)."""

from typing import TYPE_CHECKING

import pytest

from min_cpu_forth.domain.dtos import InstructionDto
from min_cpu_forth.domain.opcode import Opcode
from min_cpu_forth.errors import AssemblerError

if TYPE_CHECKING:
    from min_cpu_forth.ports import AssemblerPort, StackPort
    from min_cpu_forth.services.emulator import EmulatorService


@pytest.mark.unit
def test_dup_assembles_identically_to_the_hand_built_program(assembler: AssemblerPort) -> None:
    """``DUP`` has no jumps, so its assembled list must equal the hand-built one."""
    source = """
        POP_D  X       ; pop the top of stack
        PUSH_D X       ; push it back
        PUSH_D X       ; and push a duplicate
        HALT
    """
    hand_built = [
        InstructionDto(Opcode.POP_D, a='X'),
        InstructionDto(Opcode.PUSH_D, a='X'),
        InstructionDto(Opcode.PUSH_D, a='X'),
        InstructionDto(Opcode.HALT),
    ]

    assert list(assembler.assemble(source).program) == hand_built


@pytest.mark.unit
def test_multiply_assembles_and_runs_without_poking_any_register(
    assembler: AssemblerPort, emulator: EmulatorService, data_stack: StackPort
) -> None:
    """``*`` via repeated addition, self-contained: the backward jump resolves from a label.

    Unlike the hand-built version -- which seeds ``LOOP_ADDR`` externally -- nothing touches the
    registers here. The assembled list deliberately carries ``SET``'s ``SUB``/``ADD`` expansion,
    so this asserts behaviour, not shape.
    """
    source = """
            POP_D X        ; X := b (counter)
            POP_D Y        ; Y := a
            SUB   ACC, ACC ; ACC := 0
        LOOP:
            JZ    X, DONE
            ADD   ACC, Y
            SUB   X, 1
            SET   R, LOOP  ; materialise LOOP's absolute address into R...
            JMP   R        ; ...and branch back to it
        DONE:
            PUSH_D ACC
            HALT
    """
    data_stack.push(6)
    data_stack.push(7)
    emulator.load(assembler.assemble(source).program)

    emulator.run()

    assert data_stack.pop() == 42  # noqa: PLR2004 -- 6 * 7


@pytest.mark.unit
def test_forward_branch_offset_is_positive(assembler: AssemblerPort) -> None:
    """A ``JZ`` to a label defined later resolves to ``target - (branch_index + 1)``."""
    source = """
            JZ X, DONE     ; index 0, DONE is index 2 -> offset 2 - (0 + 1) = 1
            HALT
        DONE:
            HALT
    """
    program = assembler.assemble(source).program

    assert program[0] == InstructionDto(Opcode.JZ, a='X', offset=1)


@pytest.mark.unit
def test_backward_branch_offset_is_negative(assembler: AssemblerPort) -> None:
    """A ``JZ`` back to an earlier label assembles to a signed *negative* offset."""
    source = """
        TOP:
            SUB X, X       ; index 0
            JZ  X, TOP     ; index 1, TOP is index 0 -> offset 0 - (1 + 1) = -2
    """
    program = assembler.assemble(source).program

    assert program[1] == InstructionDto(Opcode.JZ, a='X', offset=-2)


@pytest.mark.unit
def test_set_expands_to_sub_then_add_of_the_absolute_address(assembler: AssemblerPort) -> None:
    """``SET r, <label>`` is sugar for ``SUB r, r`` then ``ADD r, <index>`` -- not a new opcode."""
    source = """
            SET R, TARGET  ; indices 0-1
            HALT           ; index 2
        TARGET:
            HALT           ; index 3
    """
    assembly = assembler.assemble(source)

    assert assembly.labels['TARGET'] == 3  # noqa: PLR2004 -- SET occupies two cells before HALT
    assert assembly.program[0] == InstructionDto(Opcode.SUB, a='R', b='R')
    assert assembly.program[1] == InstructionDto(Opcode.ADD, a='R', b=3)


@pytest.mark.unit
def test_labels_across_the_whole_unit_are_resolved(assembler: AssemblerPort) -> None:
    """A routine may name a label defined later in the same source -- Phase 1 depends on this."""
    source = """
        DUP:
            POP_D X
            PUSH_D X
            PUSH_D X
            SET R, NEXT    ; forward reference to a label defined below
            JMP R
        NEXT:
            HALT
    """
    assembly = assembler.assemble(source)

    # NEXT sits after DUP's 3 real ops + SET's 2 + JMP's 1 = index 6.
    assert dict(assembly.labels) == {'DUP': 0, 'NEXT': 6}
    assert assembly.program[4] == InstructionDto(Opcode.ADD, a='R', b=6)


@pytest.mark.unit
def test_immediate_and_register_operands_are_distinguished(assembler: AssemblerPort) -> None:
    """A bare integer is an immediate (``int``); a bare identifier is a register (``str``)."""
    program = assembler.assemble('ADD X, 5\nADD X, Y').program

    assert list(program) == [
        InstructionDto(Opcode.ADD, a='X', b=5),
        InstructionDto(Opcode.ADD, a='X', b='Y'),
    ]


@pytest.mark.unit
def test_unknown_mnemonic_raises(assembler: AssemblerPort) -> None:
    with pytest.raises(AssemblerError, match='unknown mnemonic'):
        assembler.assemble('FROB X, Y')


@pytest.mark.unit
def test_undefined_label_in_branch_raises(assembler: AssemblerPort) -> None:
    with pytest.raises(AssemblerError, match='undefined label'):
        assembler.assemble('JZ X, NOWHERE')


@pytest.mark.unit
def test_duplicate_label_raises(assembler: AssemblerPort) -> None:
    with pytest.raises(AssemblerError, match='duplicate label'):
        assembler.assemble('LOOP:\n    HALT\nLOOP:\n    HALT')


@pytest.mark.unit
def test_wrong_operand_count_raises(assembler: AssemblerPort) -> None:
    with pytest.raises(AssemblerError, match='expects 2 operand'):
        assembler.assemble('ADD X')


@pytest.mark.unit
def test_register_slot_rejects_an_integer(assembler: AssemblerPort) -> None:
    with pytest.raises(AssemblerError, match='expected a register name'):
        assembler.assemble('PUSH_D 5')

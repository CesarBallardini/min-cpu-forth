"""Unit tests for the Phase 2 CODE-primitive word set, driven through real threaded execution."""

from typing import TYPE_CHECKING, NamedTuple

import pytest

from min_cpu_forth.containers import AssemblerContainer
from min_cpu_forth.domain.register import Register
from min_cpu_forth.errors import StackError
from min_cpu_forth.services.kernel.builder import boot, boot_thread
from min_cpu_forth.services.kernel.routines import CODE_WORDS, KERNEL_SOURCE

if TYPE_CHECKING:
    from min_cpu_forth.containers import KernelContainer
    from min_cpu_forth.ports import MemoryPort, RegisterFilePort, StackPort


class MachineState(NamedTuple):
    """The observable Forth-machine state after a run -- what a test asserts against.

    ``data_stack`` is the computation's result; ``return_stack`` should be balanced (empty) after
    a well-formed run; ``registers`` exposes the reserved registers (IP/W/XT/NEXTREG); ``memory``
    is the data space (for @/! checks); ``halted`` confirms the run terminated via BYE/HALT rather
    than running away.
    """

    data_stack: StackPort
    return_stack: StackPort
    registers: RegisterFilePort
    memory: MemoryPort
    halted: bool


def _run_boot(kernel: KernelContainer, *items: str | int) -> MachineState:
    """Build a kernel with the given boot thread, run it, and capture the final MachineState."""
    machine = kernel.machine()
    emulator = machine.emulator()
    image = kernel.kernel_builder().build(colon_words=[], boot=boot_thread(*items))
    boot(emulator, image)
    emulator.run()
    return MachineState(
        data_stack=machine.data_stack(),
        return_stack=machine.return_stack(),
        registers=emulator.registers,
        memory=machine.memory(),
        halted=emulator.halted,
    )


# Each case is (boot thread, expected top-of-stack). A boot pushes literals with LIT, applies the
# word under test, then BYE. Stack comments read bottom -> top.
CASES: list[tuple[tuple[str | int, ...], int]] = [
    # --- Stack ops ---
    (('LIT', 1, 'LIT', 2, 'DROP', 'BYE'), 1),  # ( 1 2 -- 1 )
    (('LIT', 1, 'LIT', 2, 'SWAP', 'BYE'), 1),  # ( 1 2 -- 2 1 )
    (('LIT', 1, 'LIT', 2, 'OVER', 'BYE'), 1),  # ( 1 2 -- 1 2 1 )
    (('LIT', 1, 'LIT', 2, 'NIP', 'BYE'), 2),  # ( 1 2 -- 2 )
    (('LIT', 1, 'LIT', 2, 'TUCK', 'BYE'), 2),  # ( 1 2 -- 2 1 2 )
    (('LIT', 1, 'LIT', 2, 'LIT', 3, 'ROT', 'BYE'), 1),  # ( 1 2 3 -- 2 3 1 )
    (('LIT', 1, 'LIT', 2, 'LIT', 3, '-ROT', 'BYE'), 2),  # ( 1 2 3 -- 3 1 2 )
    (('LIT', 5, 'DUP', 'BYE'), 5),  # ( 5 -- 5 5 )
    # --- Arithmetic ---
    (('LIT', 3, 'LIT', 4, '+', 'BYE'), 7),
    (('LIT', 10, 'LIT', 3, '-', 'BYE'), 7),
    (('LIT', 6, 'LIT', 7, '*', 'BYE'), 42),
    (('LIT', 5, '1+', 'BYE'), 6),
    (('LIT', 5, '1-', 'BYE'), 4),
    (('LIT', 5, 'NEGATE', 'BYE'), -5),
    (('LIT', -5, 'ABS', 'BYE'), 5),
    (('LIT', 5, 'ABS', 'BYE'), 5),
    # --- Logic ---
    (('LIT', 12, 'LIT', 10, 'AND', 'BYE'), 8),  # 0b1100 & 0b1010
    (('LIT', 12, 'LIT', 10, 'OR', 'BYE'), 14),  # 0b1100 | 0b1010
    (('LIT', 0, 'INVERT', 'BYE'), -1),  # ~0
    # --- Comparison (1 = true, 0 = false) ---
    (('LIT', 3, 'LIT', 3, '=', 'BYE'), 1),
    (('LIT', 3, 'LIT', 4, '=', 'BYE'), 0),
    (('LIT', 3, 'LIT', 4, '<>', 'BYE'), 1),
    (('LIT', 3, 'LIT', 3, '<>', 'BYE'), 0),
    (('LIT', 3, 'LIT', 4, '<', 'BYE'), 1),
    (('LIT', 4, 'LIT', 3, '<', 'BYE'), 0),
    (('LIT', 3, 'LIT', 3, '<', 'BYE'), 0),
    (('LIT', 4, 'LIT', 3, '>', 'BYE'), 1),
    (('LIT', 3, 'LIT', 4, '>', 'BYE'), 0),
    (('LIT', 0, '0=', 'BYE'), 1),
    (('LIT', 5, '0=', 'BYE'), 0),
    (('LIT', -1, '0<', 'BYE'), 1),
    (('LIT', 1, '0<', 'BYE'), 0),
    # --- Return stack round-trips ---
    (('LIT', 5, '>R', 'R>', 'BYE'), 5),
    (('LIT', 5, '>R', 'R@', 'BYE'), 5),
    # --- Memory (C@/C! alias @/!); 500+ is above the kernel dictionary ---
    (('LIT', 42, 'LIT', 500, '!', 'LIT', 500, '@', 'BYE'), 42),
    (('LIT', 42, 'LIT', 501, 'C!', 'LIT', 501, 'C@', 'BYE'), 42),
]


@pytest.mark.unit
@pytest.mark.parametrize(('boot', 'expected'), CASES)
def test_primitive_stack_effect(kernel: KernelContainer, boot: tuple[str | int, ...], expected: int) -> None:
    assert _run_boot(kernel, *boot).data_stack.pop() == expected


@pytest.mark.unit
def test_a_clean_run_halts_with_a_balanced_return_stack(kernel: KernelContainer) -> None:
    """The final machine state: terminated via BYE, call stack clean, NEXTREG still set."""
    state = _run_boot(kernel, 'LIT', 3, 'LIT', 4, '+', 'BYE')

    assert state.halted is True
    assert state.return_stack.pointer == state.return_stack.base  # every ENTER matched an EXIT
    assert state.registers.read(Register.NEXT_POINTER) > 0  # START left NEXT's index in NEXTREG
    assert state.data_stack.pop() == 7  # noqa: PLR2004 -- 3 + 4


@pytest.mark.unit
def test_over_leaves_the_full_stack(kernel: KernelContainer) -> None:
    """OVER ( 1 2 -- 1 2 1 ): not just the top -- the whole residual stack is checked."""
    data_stack = _run_boot(kernel, 'LIT', 1, 'LIT', 2, 'OVER', 'BYE').data_stack

    assert [data_stack.pop(), data_stack.pop(), data_stack.pop()] == [1, 2, 1]


@pytest.mark.unit
def test_rot_leaves_the_full_stack(kernel: KernelContainer) -> None:
    """ROT ( 1 2 3 -- 2 3 1 ), popped top-to-bottom."""
    data_stack = _run_boot(kernel, 'LIT', 1, 'LIT', 2, 'LIT', 3, 'ROT', 'BYE').data_stack

    assert [data_stack.pop(), data_stack.pop(), data_stack.pop()] == [1, 3, 2]


@pytest.mark.unit
def test_tuck_leaves_the_full_stack(kernel: KernelContainer) -> None:
    """TUCK ( 1 2 -- 2 1 2 ), popped top-to-bottom."""
    data_stack = _run_boot(kernel, 'LIT', 1, 'LIT', 2, 'TUCK', 'BYE').data_stack

    assert [data_stack.pop(), data_stack.pop(), data_stack.pop()] == [2, 1, 2]


@pytest.mark.unit
def test_primitive_stack_underflow_raises(kernel: KernelContainer) -> None:
    """`+` with only one value on the stack underflows on its second pop, mid-run."""
    with pytest.raises(StackError):
        _run_boot(kernel, 'LIT', 5, '+', 'BYE')


@pytest.mark.unit
def test_every_primitive_routine_label_resolves_in_the_kernel_source() -> None:
    """Guards the data-driven table: each word's routine_label is a real label in KERNEL_SOURCE."""
    labels = AssemblerContainer().assembler().assemble(KERNEL_SOURCE).labels

    for word in CODE_WORDS:
        assert word.routine_label in labels, word


@pytest.mark.unit
def test_primitive_names_and_routine_labels_are_unique() -> None:
    names = [word.name for word in CODE_WORDS]
    labels = [word.routine_label for word in CODE_WORDS]

    assert len(names) == len(set(names))
    assert len(labels) == len(set(labels))


@pytest.mark.unit
def test_builder_installs_a_cfa_for_every_code_word(kernel: KernelContainer) -> None:
    image = kernel.kernel_builder().build(colon_words=[], boot=boot_thread('BYE'))

    assert {word.name for word in CODE_WORDS} <= image.word_cfas.keys()

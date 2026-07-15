"""Unit tests for the Phase 2 CODE-primitive word set, driven through real threaded execution."""

from typing import TYPE_CHECKING

import pytest

from min_cpu_forth.containers import AssemblerContainer
from min_cpu_forth.domain.dtos import HeaderField
from min_cpu_forth.domain.register import Register
from min_cpu_forth.errors import StackError
from min_cpu_forth.services.kernel.builder import boot_thread
from min_cpu_forth.services.kernel.routines import (
    _IMMEDIATE_FROM_NAME_FIELD,
    _LINK_FROM_NAME_FIELD,
    _SMUDGE_FROM_NAME_FIELD,
    CODE_WORDS,
    KERNEL_SOURCE,
)

if TYPE_CHECKING:
    from conftest import RunKernel

    from min_cpu_forth.containers import KernelContainer


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
    # --- Comparison (Forth true = -1, false = 0) ---
    (('LIT', 3, 'LIT', 3, '=', 'BYE'), -1),
    (('LIT', 3, 'LIT', 4, '=', 'BYE'), 0),
    (('LIT', 3, 'LIT', 4, '<>', 'BYE'), -1),
    (('LIT', 3, 'LIT', 3, '<>', 'BYE'), 0),
    (('LIT', 3, 'LIT', 4, '<', 'BYE'), -1),
    (('LIT', 4, 'LIT', 3, '<', 'BYE'), 0),
    (('LIT', 3, 'LIT', 3, '<', 'BYE'), 0),
    (('LIT', 4, 'LIT', 3, '>', 'BYE'), -1),
    (('LIT', 3, 'LIT', 4, '>', 'BYE'), 0),
    (('LIT', 0, '0=', 'BYE'), -1),
    (('LIT', 5, '0=', 'BYE'), 0),
    (('LIT', -1, '0<', 'BYE'), -1),
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
def test_primitive_stack_effect(run_kernel: RunKernel, boot: tuple[str | int, ...], expected: int) -> None:
    assert run_kernel(boot=boot).data_stack.pop() == expected


@pytest.mark.unit
def test_a_clean_run_halts_with_a_balanced_return_stack(run_kernel: RunKernel) -> None:
    """The final machine state: terminated via BYE, call stack clean, NEXTREG still set."""
    state = run_kernel(boot=('LIT', 3, 'LIT', 4, '+', 'BYE'))

    assert state.halted is True
    assert state.return_stack.pointer == state.return_stack.base  # every ENTER matched an EXIT
    assert state.registers.read(Register.NEXT_POINTER) > 0  # START left NEXT's index in NEXTREG
    assert state.data_stack.pop() == 7  # noqa: PLR2004 -- 3 + 4


@pytest.mark.unit
def test_over_leaves_the_full_stack(run_kernel: RunKernel) -> None:
    """OVER ( 1 2 -- 1 2 1 ): not just the top -- the whole residual stack is checked."""
    data_stack = run_kernel(boot=('LIT', 1, 'LIT', 2, 'OVER', 'BYE')).data_stack

    assert [data_stack.pop(), data_stack.pop(), data_stack.pop()] == [1, 2, 1]


@pytest.mark.unit
def test_rot_leaves_the_full_stack(run_kernel: RunKernel) -> None:
    """ROT ( 1 2 3 -- 2 3 1 ), popped top-to-bottom."""
    data_stack = run_kernel(boot=('LIT', 1, 'LIT', 2, 'LIT', 3, 'ROT', 'BYE')).data_stack

    assert [data_stack.pop(), data_stack.pop(), data_stack.pop()] == [1, 3, 2]


@pytest.mark.unit
def test_tuck_leaves_the_full_stack(run_kernel: RunKernel) -> None:
    """TUCK ( 1 2 -- 2 1 2 ), popped top-to-bottom."""
    data_stack = run_kernel(boot=('LIT', 1, 'LIT', 2, 'TUCK', 'BYE')).data_stack

    assert [data_stack.pop(), data_stack.pop(), data_stack.pop()] == [2, 1, 2]


@pytest.mark.unit
def test_primitive_stack_underflow_raises(run_kernel: RunKernel) -> None:
    """`+` with only one value on the stack underflows on its second pop, mid-run."""
    with pytest.raises(StackError):
        run_kernel(boot=('LIT', 5, '+', 'BYE'))


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


@pytest.mark.unit
def test_find_header_offsets_stay_derived_from_headerfield() -> None:
    """FIND's assembler bakes in header offsets; guard they stay tied to HeaderField."""
    assert _IMMEDIATE_FROM_NAME_FIELD == HeaderField.NAME_LENGTH - HeaderField.IMMEDIATE
    assert _SMUDGE_FROM_NAME_FIELD == HeaderField.NAME_LENGTH - HeaderField.SMUDGE
    assert _LINK_FROM_NAME_FIELD == HeaderField.NAME_LENGTH

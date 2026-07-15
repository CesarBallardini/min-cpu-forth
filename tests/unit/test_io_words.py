"""Unit tests for the Phase 4 I/O and dictionary-search words: KEY/EMIT/NUMBER/WORD/FIND."""

from typing import TYPE_CHECKING

import pytest

from min_cpu_forth import layout
from min_cpu_forth.domain.dtos import ColonWordDto, HeaderField
from min_cpu_forth.domain.types import Address, Cell
from min_cpu_forth.errors import InputExhaustedError

if TYPE_CHECKING:
    from conftest import RunKernel

    from min_cpu_forth.containers import KernelContainer
    from min_cpu_forth.domain.dtos import KernelImageDto

_SPACE = 32
_SCRATCH = 500  # an address above the kernel dictionary, for placing counted strings


@pytest.mark.unit
def test_emit_writes_a_character(run_kernel: RunKernel) -> None:
    state = run_kernel(boot=('LIT', ord('!'), 'EMIT', 'BYE'))

    assert list(state.output.buffer) == [ord('!')]


@pytest.mark.unit
def test_key_reads_a_character(run_kernel: RunKernel) -> None:
    state = run_kernel(boot=('KEY', 'EMIT', 'BYE'), feed='A')  # KEY reads it, EMIT echoes it back

    assert list(state.output.buffer) == [ord('A')]


@pytest.mark.unit
def test_emit_accumulates_output_in_order(run_kernel: RunKernel) -> None:
    state = run_kernel(boot=('LIT', ord('H'), 'EMIT', 'LIT', ord('I'), 'EMIT', 'BYE'))

    assert list(state.output.buffer) == [ord('H'), ord('I')]


@pytest.mark.unit
def test_key_on_empty_input_raises(run_kernel: RunKernel) -> None:
    """KEY with nothing to read surfaces InputExhaustedError mid-run."""
    with pytest.raises(InputExhaustedError):
        run_kernel(boot=('KEY', 'BYE'))


@pytest.mark.unit
@pytest.mark.parametrize(
    ('text', 'value', 'flag'),
    [
        ('42', 42, 1),
        ('123', 123, 1),
        ('1000', 1000, 1),  # exercises the *10 accumulation across several digits
        ('007', 7, 1),  # leading zeros
        ('0', 0, 1),
        ('-7', -7, 1),
        ('-0', 0, 1),
        ('4x', 0, 0),  # non-digit -> fail
        ('DUP', 0, 0),  # a word-shaped non-number -> fail
        ('', 0, 0),  # empty -> fail
        ('-', 0, 0),  # sign only -> fail
    ],
)
def test_number_parses_signed_decimal(run_kernel: RunKernel, text: str, value: int, flag: int) -> None:
    state = run_kernel(boot=('LIT', _SCRATCH, 'NUMBER', 'BYE'), string_at=(_SCRATCH, text))

    assert state.data_stack.pop() == flag
    assert state.data_stack.pop() == value


@pytest.mark.unit
def test_word_tokenizes_skipping_leading_delimiters(run_kernel: RunKernel, kernel: KernelContainer) -> None:
    state = run_kernel(boot=('LIT', _SPACE, 'WORD', 'BYE'), feed='  DUP ')

    address = state.data_stack.pop()
    assert address == layout.WORD_BUFFER_BASE
    assert kernel.counted_strings().read(Address(address)) == 'DUP'


@pytest.mark.unit
def test_word_advances_through_successive_tokens(run_kernel: RunKernel, kernel: KernelContainer) -> None:
    state = run_kernel(boot=('LIT', _SPACE, 'WORD', 'DROP', 'LIT', _SPACE, 'WORD', 'BYE'), feed='DUP DROP ')

    assert kernel.counted_strings().read(Address(state.data_stack.pop())) == 'DROP'


@pytest.mark.unit
def test_find_locates_a_word_and_flags_it_normal(run_kernel: RunKernel, kernel: KernelContainer) -> None:
    """WORD + FIND on a known word returns its CFA (== the dictionary port's) and the normal flag."""
    state = run_kernel(boot=('LIT', _SPACE, 'WORD', 'FIND', 'BYE'), feed='DUP ')

    flag = state.data_stack.pop()
    xt = state.data_stack.pop()
    found = kernel.dictionary().find('DUP')
    assert found is not None
    assert xt == found.cfa
    assert flag == -1


@pytest.mark.unit
def test_find_returns_zero_for_a_missing_word(run_kernel: RunKernel) -> None:
    state = run_kernel(boot=('LIT', _SPACE, 'WORD', 'FIND', 'BYE'), feed='NOPE ')

    assert state.data_stack.pop() == 0  # flag: not found
    assert state.data_stack.pop() == 0  # xt: 0


@pytest.mark.unit
def test_find_flags_an_immediate_word(run_kernel: RunKernel, kernel: KernelContainer) -> None:
    """An IMMEDIATE word is reported with flag 1 (vs -1 for a normal word)."""
    state = run_kernel(
        boot=('LIT', _SPACE, 'WORD', 'FIND', 'BYE'),
        feed='IMM ',
        colon_words=(ColonWordDto(name='IMM', words=('DUP',), immediate=True),),
    )

    assert state.data_stack.pop() == 1  # immediate flag
    found = kernel.dictionary().find('IMM')
    assert found is not None
    assert state.data_stack.pop() == found.cfa


@pytest.mark.unit
def test_find_locates_a_normal_colon_word(run_kernel: RunKernel, kernel: KernelContainer) -> None:
    """FIND resolves colon words (ENTER-based CFAs) too, with the normal flag."""
    state = run_kernel(
        boot=('LIT', _SPACE, 'WORD', 'FIND', 'BYE'),
        feed='SQ ',
        colon_words=(ColonWordDto(name='SQ', words=('DUP', '*')),),
    )

    assert state.data_stack.pop() == -1  # normal (non-immediate)
    found = kernel.dictionary().find('SQ')
    assert found is not None
    assert state.data_stack.pop() == found.cfa


@pytest.mark.unit
def test_find_does_not_match_a_shorter_prefix(run_kernel: RunKernel) -> None:
    """ "DU" must not match "DUP": FIND compares the full length, not a prefix."""
    state = run_kernel(boot=('LIT', _SCRATCH, 'FIND', 'BYE'), string_at=(_SCRATCH, 'DU'))

    assert state.data_stack.pop() == 0  # flag: not found
    assert state.data_stack.pop() == 0  # xt: 0


def _smudge(memory_owner: KernelContainer, name_field: int) -> None:
    """Set the smudge cell of the word whose name field is at ``name_field``."""
    smudge_cell = Address(name_field - (HeaderField.NAME_LENGTH - HeaderField.SMUDGE))
    memory_owner.machine().memory().write(smudge_cell, Cell(1))


@pytest.mark.unit
def test_find_skips_smudged_words(run_kernel: RunKernel) -> None:
    """A smudged (hidden, mid-compile) word is not found -- FIND walks past it."""

    def smudge_latest(kernel: KernelContainer, image: KernelImageDto) -> None:
        del image
        _smudge(kernel, kernel.machine().memory().read(Address(layout.LATEST_ADDR)))

    state = run_kernel(
        boot=('LIT', _SPACE, 'WORD', 'FIND', 'BYE'),
        feed='HID ',
        colon_words=(ColonWordDto(name='HID', words=('DUP',)),),
        after_build=smudge_latest,
    )

    assert state.data_stack.pop() == 0  # flag: not found (skipped)
    assert state.data_stack.pop() == 0  # xt: 0


@pytest.mark.unit
def test_find_returns_an_older_definition_when_the_newest_is_smudged(
    run_kernel: RunKernel, kernel: KernelContainer
) -> None:
    """The point of smudge: FIND walks *past* a hidden redefinition to the older visible one."""

    def smudge_latest(container: KernelContainer, image: KernelImageDto) -> None:
        del image
        _smudge(container, container.machine().memory().read(Address(layout.LATEST_ADDR)))

    state = run_kernel(
        boot=('LIT', _SPACE, 'WORD', 'FIND', 'BYE'),
        feed='DUP ',
        colon_words=(ColonWordDto(name='DUP', words=('DUP',)),),  # a colon DUP shadows the CODE DUP
        after_build=smudge_latest,
    )

    assert state.data_stack.pop() == -1  # a normal word (the CODE DUP)
    xt = state.data_stack.pop()
    # Newest-first, the two 'DUP' headers are [smudged colon DUP, CODE DUP]; FIND returns the latter.
    dup_cfas = [header.cfa for header in kernel.dictionary().headers() if header.name == 'DUP']
    assert xt == dup_cfas[1]  # the older (CODE) DUP
    assert xt != dup_cfas[0]  # not the newest (smudged) one


@pytest.mark.unit
def test_find_skips_a_smudged_word_mid_chain(run_kernel: RunKernel, kernel: KernelContainer) -> None:
    """Smudging a word in the middle of the chain hides only it; newer/older words still resolve."""

    def smudge_over(container: KernelContainer, image: KernelImageDto) -> None:
        del image
        over = container.dictionary().find('OVER')  # a mid-chain CODE word
        assert over is not None
        _smudge(container, over.cfa - 1 - len('OVER'))

    state = run_kernel(
        boot=('LIT', _SPACE, 'WORD', 'FIND', 'LIT', _SPACE, 'WORD', 'FIND', 'BYE'),
        feed='OVER DUP ',
        after_build=smudge_over,
    )

    dup = kernel.dictionary().find('DUP')
    assert dup is not None
    assert state.data_stack.pop() == -1  # DUP still found
    assert state.data_stack.pop() == dup.cfa
    assert state.data_stack.pop() == 0  # OVER flag: not found (smudged)
    assert state.data_stack.pop() == 0  # OVER xt: 0

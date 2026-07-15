"""Integration: the WORD/FIND/NUMBER pipeline Phase 5's INTERPRET will thread, no test doubles."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from conftest import RunKernel

    from min_cpu_forth.containers import KernelContainer

_SPACE = ord(' ')


@pytest.mark.integration
def test_word_then_number_parses_a_typed_token(run_kernel: RunKernel) -> None:
    """WORD's counted-string output feeds straight into NUMBER: typing "42" yields 42."""
    state = run_kernel(boot=('LIT', _SPACE, 'WORD', 'NUMBER', 'BYE'), feed='42 ')

    assert state.data_stack.pop() == 1  # NUMBER success flag
    assert state.data_stack.pop() == 42  # noqa: PLR2004 -- the parsed value


@pytest.mark.integration
def test_word_then_find_resolves_a_known_word(run_kernel: RunKernel, kernel: KernelContainer) -> None:
    """Typing a defined word's name looks it up: WORD FIND returns its execution token."""
    state = run_kernel(boot=('LIT', _SPACE, 'WORD', 'FIND', 'BYE'), feed='DUP ')

    flag = state.data_stack.pop()
    xt = state.data_stack.pop()
    found = kernel.dictionary().find('DUP')
    assert found is not None
    assert flag != 0  # found
    assert xt == found.cfa


@pytest.mark.integration
def test_find_or_number_falls_back_to_number_for_a_literal(run_kernel: RunKernel) -> None:
    """The INTERPRET decision: FIND misses on "42", so NUMBER parses it.

    Threaded without control flow -- ``WORD DUP FIND DROP DROP NUMBER`` keeps the token address
    under FIND's (0 0) miss result, then parses it -- which is exactly the find-or-number choice
    the outer interpreter makes per token.
    """
    state = run_kernel(boot=('LIT', _SPACE, 'WORD', 'DUP', 'FIND', 'DROP', 'DROP', 'NUMBER', 'BYE'), feed='42 ')

    assert state.data_stack.pop() == 1  # NUMBER success
    assert state.data_stack.pop() == 42  # noqa: PLR2004 -- parsed as a literal after FIND missed

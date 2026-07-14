"""Unit tests for the ForthService's word dictionary and colon definitions."""

from typing import TYPE_CHECKING

import pytest

from min_cpu_forth.domain.register import Register
from min_cpu_forth.errors import UnknownWordError

if TYPE_CHECKING:
    from min_cpu_forth.ports import RegisterFilePort, StackPort
    from min_cpu_forth.services.forth import ForthService


@pytest.mark.unit
def test_dup_plus(forth: ForthService, data_stack: StackPort) -> None:
    data_stack.push(3)

    forth.dictionary['DUP']()
    forth.dictionary['+']()

    assert data_stack.pop() == 6


@pytest.mark.unit
def test_colon_definition_square(forth: ForthService, data_stack: StackPort) -> None:
    forth.add_colon_def('SQUARE', ['DUP', '*'])
    data_stack.push(3)

    forth.dictionary['SQUARE']()

    assert data_stack.pop() == 9


@pytest.mark.unit
def test_colon_definition_referencing_unknown_word_raises(forth: ForthService) -> None:
    forth.add_colon_def('BROKEN', ['NOT-A-WORD'])

    with pytest.raises(UnknownWordError, match='NOT-A-WORD'):
        forth.dictionary['BROKEN']()


@pytest.mark.unit
def test_swap(forth: ForthService, data_stack: StackPort) -> None:
    data_stack.push(1)
    data_stack.push(2)

    forth.dictionary['SWAP']()

    assert data_stack.pop() == 1
    assert data_stack.pop() == 2


@pytest.mark.unit
def test_store_and_fetch(forth: ForthService, data_stack: StackPort) -> None:
    data_stack.push(99)  # value
    data_stack.push(0)  # address
    forth.dictionary['!']()

    data_stack.push(0)  # address
    forth.dictionary['@']()

    assert data_stack.pop() == 99


@pytest.mark.unit
def test_docol_and_exit_round_trip_through_return_stack(
    forth: ForthService, forth_registers: RegisterFilePort
) -> None:
    forth_registers.write(Register.IP, 42)

    forth.dictionary['DOCOL'](7)
    assert forth_registers.read(Register.IP) == 7

    forth.dictionary['EXIT']()
    assert forth_registers.read(Register.IP) == 42


@pytest.mark.unit
def test_to_r_and_r_from(forth: ForthService, data_stack: StackPort, return_stack: StackPort) -> None:
    data_stack.push(5)

    forth.dictionary['>R']()
    assert data_stack.pointer == data_stack.base  # data stack is empty
    assert return_stack.peek() == 5

    forth.dictionary['R>']()

    assert data_stack.pop() == 5

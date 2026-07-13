"""Unit tests for the ForthExecutioner's word dictionary and colon definitions."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from min_cpu_forth.cpu import CPU
    from min_cpu_forth.forth import ForthExecutioner


@pytest.mark.unit
def test_dup_plus(cpu: CPU, forth: ForthExecutioner) -> None:
    cpu.data_stack.push(3)

    forth.dict['DUP']()
    forth.dict['+']()

    assert cpu.data_stack.pop() == 6


@pytest.mark.unit
def test_colon_definition_square(cpu: CPU, forth: ForthExecutioner) -> None:
    forth.add_colon_def('SQUARE', ['DUP', '*'])
    cpu.data_stack.push(3)

    forth.dict['SQUARE']()

    assert cpu.data_stack.pop() == 9


@pytest.mark.unit
def test_colon_definition_referencing_unknown_word_raises(forth: ForthExecutioner) -> None:
    forth.add_colon_def('BROKEN', ['NOT-A-WORD'])

    with pytest.raises(ValueError, match='NOT-A-WORD'):
        forth.dict['BROKEN']()


@pytest.mark.unit
def test_swap(cpu: CPU, forth: ForthExecutioner) -> None:
    cpu.data_stack.push(1)
    cpu.data_stack.push(2)

    forth.dict['SWAP']()

    assert cpu.data_stack.pop() == 1
    assert cpu.data_stack.pop() == 2


@pytest.mark.unit
def test_store_and_fetch(cpu: CPU, forth: ForthExecutioner) -> None:
    cpu.data_stack.push(99)  # value
    cpu.data_stack.push(0)  # address
    forth.dict['!']()

    cpu.data_stack.push(0)  # address
    forth.dict['@']()

    assert cpu.data_stack.pop() == 99


@pytest.mark.unit
def test_docol_and_exit_round_trip_through_return_stack(cpu: CPU, forth: ForthExecutioner) -> None:
    cpu.ip = 42

    forth.dict['DOCOL'](7)
    assert cpu.ip == 7

    forth.dict['EXIT']()
    assert cpu.ip == 42


@pytest.mark.unit
def test_to_r_and_r_from(cpu: CPU, forth: ForthExecutioner) -> None:
    cpu.data_stack.push(5)

    forth.dict['>R']()
    assert cpu.data_stack.sp == cpu.data_stack.base  # data stack is empty
    assert cpu.return_stack.peek() == 5

    forth.dict['R>']()

    assert cpu.data_stack.pop() == 5

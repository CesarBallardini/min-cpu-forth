"""Unit tests for the CPU's data and return stacks."""

import pytest

from min_cpu_forth.cpu import CPU, Stack, StackError


@pytest.mark.unit
def test_push_pop_round_trips() -> None:
    stack = Stack([0] * 8, base=8, size=4)

    stack.push(42)

    assert stack.peek() == 42
    assert stack.pop() == 42


@pytest.mark.unit
def test_pop_underflow_raises() -> None:
    stack = Stack([0] * 8, base=8, size=4)

    with pytest.raises(StackError):
        stack.pop()


@pytest.mark.unit
def test_push_overflow_raises() -> None:
    stack = Stack([0] * 8, base=8, size=2)

    stack.push(1)
    stack.push(2)

    with pytest.raises(StackError):
        stack.push(3)


@pytest.mark.unit
def test_data_and_return_stacks_do_not_collide(cpu: CPU) -> None:
    cpu.data_stack.push(1)
    cpu.return_stack.push(2)
    cpu.data_stack.push(3)

    assert cpu.return_stack.pop() == 2
    assert cpu.data_stack.pop() == 3
    assert cpu.data_stack.pop() == 1


@pytest.mark.unit
def test_add_updates_named_register(cpu: CPU) -> None:
    cpu.ip = 10

    cpu.add('ip', 4)

    assert cpu.ip == 14


@pytest.mark.unit
def test_jz_branches_only_when_register_is_zero(cpu: CPU) -> None:
    cpu.ip = 100
    cpu.w = 0

    cpu.jz('w', 5)

    assert cpu.ip == 105


@pytest.mark.unit
def test_jz_does_not_branch_when_register_is_nonzero(cpu: CPU) -> None:
    cpu.ip = 100
    cpu.w = 1

    cpu.jz('w', 5)

    assert cpu.ip == 100


@pytest.mark.unit
def test_halt_sets_halted_flag(cpu: CPU) -> None:
    assert cpu.halted is False

    cpu.halt()

    assert cpu.halted is True

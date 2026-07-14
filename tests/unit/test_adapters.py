"""Unit tests for the concrete port adapters (memory, stack, registers, character I/O)."""

from typing import TYPE_CHECKING

import pytest

from min_cpu_forth.adapters.io import (
    BufferCharacterOutputAdapter,
    QueueCharacterInputAdapter,
)
from min_cpu_forth.adapters.memory import ListMemoryAdapter
from min_cpu_forth.adapters.registers import DictRegisterFileAdapter
from min_cpu_forth.adapters.stack import DownwardStackAdapter
from min_cpu_forth.errors import InputExhaustedError, StackError

if TYPE_CHECKING:
    from min_cpu_forth.ports import MemoryPort, StackPort


@pytest.mark.unit
def test_memory_reads_back_what_it_writes() -> None:
    memory = ListMemoryAdapter(size=16)

    memory.write(5, 99)

    assert memory.read(5) == 99
    assert memory.size == 16


@pytest.mark.unit
def test_registers_default_to_zero_then_hold_writes() -> None:
    registers = DictRegisterFileAdapter()

    assert registers.read('X') == 0

    registers.write('X', 7)

    assert registers.read('X') == 7


@pytest.mark.unit
def test_stack_push_pop_round_trips() -> None:
    stack = DownwardStackAdapter(ListMemoryAdapter(size=8), base=8, size=4)

    stack.push(42)

    assert stack.peek() == 42
    assert stack.pop() == 42


@pytest.mark.unit
def test_stack_pop_underflow_raises() -> None:
    stack = DownwardStackAdapter(ListMemoryAdapter(size=8), base=8, size=4)

    with pytest.raises(StackError):
        stack.pop()


@pytest.mark.unit
def test_stack_push_overflow_raises() -> None:
    stack = DownwardStackAdapter(ListMemoryAdapter(size=8), base=8, size=2)

    stack.push(1)
    stack.push(2)

    with pytest.raises(StackError):
        stack.push(3)


@pytest.mark.unit
def test_data_and_return_stacks_do_not_collide(data_stack: StackPort, return_stack: StackPort) -> None:
    data_stack.push(1)
    return_stack.push(2)
    data_stack.push(3)

    assert return_stack.pop() == 2
    assert data_stack.pop() == 3
    assert data_stack.pop() == 1


@pytest.mark.unit
def test_stacks_share_the_same_backing_memory(memory: MemoryPort, data_stack: StackPort) -> None:
    data_stack.push(77)

    # The pushed value lands one cell below the (empty) base, in the shared memory.
    assert memory.read(data_stack.base - 1) == 77


@pytest.mark.unit
def test_input_queue_feeds_in_order_then_exhausts() -> None:
    device = QueueCharacterInputAdapter([ord('A')])
    device.feed([ord('B')])

    assert device.read() == ord('A')
    assert device.read() == ord('B')
    with pytest.raises(InputExhaustedError):
        device.read()


@pytest.mark.unit
def test_output_buffer_collects_in_order() -> None:
    device = BufferCharacterOutputAdapter()

    device.write(ord('h'))
    device.write(ord('i'))

    assert list(device.buffer) == [ord('h'), ord('i')]

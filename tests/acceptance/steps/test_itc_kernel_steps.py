"""Step definitions for itc_kernel.feature."""

from dataclasses import dataclass, field

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

# Real (non-TYPE_CHECKING) imports: pytest-bdd resolves step-parameter annotations via
# inspect.signature() at call time (PEP 649 lazy annotations, py3.14).
from min_cpu_forth.containers import KernelContainer
from min_cpu_forth.domain.dtos import ColonWordDto
from min_cpu_forth.domain.register import Register
from min_cpu_forth.services.kernel.builder import boot_thread

scenarios('../features/itc_kernel.feature')


@dataclass
class KernelState:
    container: KernelContainer
    colon_words: list[ColonWordDto] = field(default_factory=list)
    top: int | None = None


@pytest.fixture
def state() -> KernelState:
    return KernelState(container=KernelContainer())


def _thread_item(token: str) -> int | str:
    try:
        return int(token)
    except ValueError:
        return token


@given(parsers.parse('a threaded colon definition "{name}" of "{words}"'))
def define_colon(state: KernelState, name: str, words: str) -> None:
    state.colon_words.append(ColonWordDto(name=name, words=tuple(words.split())))


@when(parsers.parse('I boot the kernel with "{boot}"'))
def boot_kernel(state: KernelState, boot: str) -> None:
    builder = state.container.kernel_builder()
    machine = state.container.machine()
    emulator = machine.emulator()

    image = builder.build(
        colon_words=state.colon_words,
        boot=boot_thread(*(_thread_item(token) for token in boot.split())),
    )
    emulator.load(image.program)
    emulator.registers.write(Register.IP, image.boot_ip)
    emulator.run()
    state.top = machine.data_stack().pop()


@then(parsers.parse('the threaded data stack top is {value:d}'))
def data_stack_top_is(state: KernelState, value: int) -> None:
    assert state.top == value

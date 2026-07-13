"""Step definitions for square.feature."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

# Real (non-TYPE_CHECKING) imports: pytest-bdd binds parser args to step
# parameters via inspect.signature(), which -- under PEP 649 lazy annotation
# evaluation (py3.14) -- resolves annotations at call time, not just for
# static type checking. A TYPE_CHECKING-only import would NameError here.
from min_cpu_forth.cpu import CPU
from min_cpu_forth.forth import ForthExecutioner

scenarios('../features/square.feature')


@pytest.fixture
def caught_error() -> dict[str, Exception | None]:
    return {'raised': None}


@given(parsers.parse('a colon definition "{name}" made of the words "{words}"'))
def colon_def(forth: ForthExecutioner, name: str, words: str) -> None:
    forth.add_colon_def(name, words.split())


@when(parsers.parse('I push {value:d} and run "{name}"'))
def push_and_run(cpu: CPU, forth: ForthExecutioner, value: int, name: str) -> None:
    cpu.data_stack.push(value)
    forth.dict[name]()


@when(parsers.parse('I try to run "{name}"'))
def try_run(forth: ForthExecutioner, name: str, caught_error: dict) -> None:
    try:
        forth.dict[name]()
    except ValueError as exc:
        caught_error['raised'] = exc


@then(parsers.parse('the top of the data stack is {value:d}'))
def top_of_stack_is(cpu: CPU, value: int) -> None:
    assert cpu.data_stack.pop() == value


@then('it fails because the word was not found')
def it_fails_not_found(caught_error: dict) -> None:
    assert isinstance(caught_error['raised'], ValueError)

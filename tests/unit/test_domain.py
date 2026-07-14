"""Unit tests for the domain enums' string-identity semantics (the code relies on these)."""

import pytest

from min_cpu_forth.domain.opcode import Opcode
from min_cpu_forth.domain.register import Register


@pytest.mark.unit
def test_opcode_is_a_str_enum() -> None:
    assert Opcode.LOAD == 'LOAD'
    assert Opcode('LOAD') is Opcode.LOAD
    # A member is interchangeable with its string value as a dict key (the assembler's MNEMONICS).
    assert 'LOAD' in {Opcode.LOAD: 1}


@pytest.mark.unit
def test_register_is_a_str_enum() -> None:
    assert Register.IP == 'IP'
    assert Register.NEXT_POINTER == 'NEXTREG'
    assert str(Register.IP) == 'IP'  # StrEnum stringifies to its value, not 'Register.IP'

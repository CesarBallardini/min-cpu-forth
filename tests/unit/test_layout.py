"""Unit tests for the memory-map constants."""

import pytest

from min_cpu_forth import layout


@pytest.mark.unit
def test_system_variables_sit_below_the_dictionary() -> None:
    assert layout.DP_ADDR < layout.DICTIONARY_BASE
    assert layout.LATEST_ADDR < layout.DICTIONARY_BASE
    assert layout.DP_ADDR != layout.LATEST_ADDR


@pytest.mark.unit
def test_dictionary_region_stays_below_the_data_stack() -> None:
    data_stack_floor = layout.DATA_STACK_BASE - layout.DATA_STACK_SIZE

    assert layout.DICTIONARY_BASE < layout.DICTIONARY_TOP
    assert data_stack_floor == layout.DICTIONARY_TOP  # dictionary ends where the data stack begins


@pytest.mark.unit
def test_stacks_do_not_overlap_the_dictionary_or_each_other() -> None:
    assert layout.DATA_STACK_BASE - layout.DATA_STACK_SIZE >= layout.DICTIONARY_TOP
    assert layout.RETURN_STACK_BASE - layout.RETURN_STACK_SIZE >= layout.DATA_STACK_BASE
    assert layout.MEMORY_SIZE == layout.RETURN_STACK_BASE

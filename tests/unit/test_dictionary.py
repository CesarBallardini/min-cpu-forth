"""Unit tests for the MemoryDictionaryAdapter: header layout and link-chain search."""

import pytest

from min_cpu_forth import layout
from min_cpu_forth.adapters.dictionary import MemoryDictionaryAdapter
from min_cpu_forth.adapters.memory import ListMemoryAdapter
from min_cpu_forth.adapters.system_variables import MemorySystemVariablesAdapter
from min_cpu_forth.domain.dtos import HeaderField
from min_cpu_forth.domain.types import Address, ProgramIndex


def _fresh() -> tuple[ListMemoryAdapter, MemoryDictionaryAdapter]:
    memory = ListMemoryAdapter(layout.MEMORY_SIZE)
    return memory, MemoryDictionaryAdapter(memory, MemorySystemVariablesAdapter(memory))


@pytest.mark.unit
def test_append_word_lays_out_the_header_at_the_documented_offsets() -> None:
    memory, dictionary = _fresh()

    cfa = dictionary.append_word('DUP', ProgramIndex(42))

    base = layout.DICTIONARY_BASE  # first word starts at the bottom of dictionary space
    assert memory.read(Address(base + HeaderField.LINK)) == 0  # first word -> no predecessor
    assert memory.read(Address(base + HeaderField.IMMEDIATE)) == 0
    assert memory.read(Address(base + HeaderField.SMUDGE)) == 0
    assert memory.read(Address(base + HeaderField.NAME_LENGTH)) == len('DUP')
    assert [memory.read(Address(base + HeaderField.NAME + i)) for i in range(3)] == [ord(c) for c in 'DUP']
    assert cfa == base + HeaderField.NAME + len('DUP')  # the code-field cell
    assert memory.read(cfa) == 42  # noqa: PLR2004 -- holds the program index we appended


@pytest.mark.unit
def test_append_word_writes_a_colon_thread_after_the_code_field() -> None:
    memory, dictionary = _fresh()
    dup = dictionary.append_word('DUP', ProgramIndex(1))
    exit_cfa = dictionary.append_word('EXIT', ProgramIndex(2))

    square = dictionary.append_word('SQ', ProgramIndex(99), thread=(dup, dup, exit_cfa))

    assert [memory.read(Address(square + offset)) for offset in (1, 2, 3)] == [dup, dup, exit_cfa]


@pytest.mark.unit
def test_headers_walk_newest_first_and_find_locates_a_word() -> None:
    _, dictionary = _fresh()
    dictionary.append_word('A', ProgramIndex(1))
    dictionary.append_word('B', ProgramIndex(2))
    dictionary.append_word('C', ProgramIndex(3))

    assert [header.name for header in dictionary.headers()] == ['C', 'B', 'A']

    found = dictionary.find('B')
    assert found is not None
    assert found.name == 'B'
    assert dictionary.find('missing') is None


@pytest.mark.unit
def test_append_word_marks_immediate_words() -> None:
    _, dictionary = _fresh()

    dictionary.append_word('IF', ProgramIndex(9), immediate=True)

    header = dictionary.find('IF')
    assert header is not None
    assert header.immediate is True

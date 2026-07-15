"""Unit tests for the ITC kernel: real threaded execution through NEXT/DOCOL/EXIT (Phases 1-2)."""

from typing import TYPE_CHECKING

import pytest

from min_cpu_forth import layout
from min_cpu_forth.adapters.counted_string import MemoryCountedStringAdapter
from min_cpu_forth.adapters.dictionary import MemoryDictionaryAdapter
from min_cpu_forth.adapters.memory import ListMemoryAdapter
from min_cpu_forth.adapters.system_variables import MemorySystemVariablesAdapter
from min_cpu_forth.domain.dtos import AssemblyDto, ColonWordDto, LiteralCellDto, WordReferenceDto
from min_cpu_forth.domain.register import Register
from min_cpu_forth.domain.types import Address, Cell, ProgramIndex
from min_cpu_forth.errors import KernelError
from min_cpu_forth.services.kernel.builder import KernelBuilder, boot, boot_thread
from min_cpu_forth.services.kernel.routines import CODE_WORDS

if TYPE_CHECKING:
    from min_cpu_forth.containers import KernelContainer


class _StartMisplacedAssembler:
    """An ``AssemblerPort`` stub whose ``START`` label is not at program index 0."""

    def assemble(self, source: str) -> AssemblyDto:
        del source
        return AssemblyDto(program=(), labels={'START': ProgramIndex(5), 'ENTER': ProgramIndex(1)})


@pytest.mark.unit
def test_square_runs_end_to_end_through_real_next(kernel: KernelContainer) -> None:
    """3 SQUARE -> 9 threaded through LIT/DOCOL/DUP/*/EXIT/BYE -- the first true ITC execution.

    Every earlier version executed a colon definition by iterating a Python list of word names;
    this drives the real ``NEXT`` double-indirection over a dictionary laid out in ``cpu.mem``.
    """
    machine = kernel.machine()
    emulator = machine.emulator()

    image = kernel.kernel_builder().build(
        colon_words=[ColonWordDto(name='SQUARE', words=('DUP', '*'))],
        boot=boot_thread('LIT', 3, 'SQUARE', 'BYE'),
    )
    boot(emulator, image)
    emulator.run()

    assert machine.data_stack().pop() == 9  # noqa: PLR2004 -- 3 squared


@pytest.mark.unit
def test_installed_word_is_found_in_the_dictionary(kernel: KernelContainer) -> None:
    """The builder installs each word; its header decodes back through the dictionary port."""
    dictionary = kernel.dictionary()

    image = kernel.kernel_builder().build(colon_words=[], boot=boot_thread('BYE'))

    header = dictionary.find('LIT')  # the first CODE word installed
    assert header is not None
    assert header.name == 'LIT'
    assert header.immediate is False
    assert header.link == 0  # first word -> no predecessor
    assert header.cfa == image.word_cfas['LIT']


@pytest.mark.unit
def test_colon_thread_holds_cfas_terminated_by_exit(kernel: KernelContainer) -> None:
    """A colon word's parameter field is a thread of the referenced CFAs, ending in EXIT's CFA."""
    memory = kernel.machine().memory()

    image = kernel.kernel_builder().build(
        colon_words=[ColonWordDto(name='SQUARE', words=('DUP', '*'))],
        boot=boot_thread('BYE'),
    )

    cfa = image.word_cfas['SQUARE']
    thread = [memory.read(Address(cfa + offset)) for offset in (1, 2, 3)]
    assert thread == [image.word_cfas['DUP'], image.word_cfas['*'], image.word_cfas['EXIT']]


@pytest.mark.unit
def test_nested_colon_definitions_execute_and_balance_the_return_stack(
    kernel: KernelContainer,
) -> None:
    """A colon word calling another colon word nests DOCOL/EXIT; the return stack ends balanced."""
    machine = kernel.machine()
    emulator = machine.emulator()
    return_stack = machine.return_stack()

    image = kernel.kernel_builder().build(
        colon_words=[
            ColonWordDto(name='SQUARE', words=('DUP', '*')),
            ColonWordDto(name='FOURTH', words=('SQUARE', 'SQUARE')),  # calls SQUARE, defined above
        ],
        boot=boot_thread('LIT', 2, 'FOURTH', 'BYE'),
    )
    boot(emulator, image)
    emulator.run()

    assert machine.data_stack().pop() == 16  # noqa: PLR2004 -- ((2^2)^2)
    assert return_stack.pointer == return_stack.base  # every ENTER matched by an EXIT


@pytest.mark.unit
def test_two_literals_multiplied_directly_at_the_top_level(kernel: KernelContainer) -> None:
    """LIT twice then ``*`` -- exercises LIT and a CODE word without any colon indirection."""
    machine = kernel.machine()
    emulator = machine.emulator()

    image = kernel.kernel_builder().build(colon_words=[], boot=boot_thread('LIT', 5, 'LIT', 3, '*', 'BYE'))
    boot(emulator, image)
    emulator.run()

    assert machine.data_stack().pop() == 15  # noqa: PLR2004 -- 5 * 3


@pytest.mark.unit
def test_dictionary_headers_walk_installed_words_newest_first(kernel: KernelContainer) -> None:
    """The LATEST link chain visits every word, newest first -- Phase 4's FIND builds on this."""
    dictionary = kernel.dictionary()

    kernel.kernel_builder().build(colon_words=[], boot=boot_thread('BYE'))

    assert [header.name for header in dictionary.headers()] == [w.name for w in reversed(CODE_WORDS)]


@pytest.mark.unit
def test_colon_referencing_an_uninstalled_word_raises(kernel: KernelContainer) -> None:
    builder = kernel.kernel_builder()

    with pytest.raises(KernelError, match='NOSUCH'):
        builder.build(colon_words=[ColonWordDto(name='BAD', words=('NOSUCH',))], boot=boot_thread('BYE'))


@pytest.mark.unit
def test_boot_referencing_an_uninstalled_word_raises(kernel: KernelContainer) -> None:
    builder = kernel.kernel_builder()

    with pytest.raises(KernelError, match='NOSUCH'):
        builder.build(colon_words=[], boot=boot_thread('NOSUCH', 'BYE'))


@pytest.mark.unit
def test_build_rejects_a_kernel_whose_start_is_not_at_index_zero() -> None:
    """The boot guard: ``START`` must assemble at program index 0 (``EmulatorService`` starts there)."""
    memory = ListMemoryAdapter(layout.MEMORY_SIZE)
    dictionary = MemoryDictionaryAdapter(
        memory, MemorySystemVariablesAdapter(memory), MemoryCountedStringAdapter(memory)
    )
    builder = KernelBuilder(assembler=_StartMisplacedAssembler(), dictionary=dictionary)

    with pytest.raises(KernelError, match='START'):
        builder.build(colon_words=[], boot=boot_thread('BYE'))


@pytest.mark.unit
def test_colon_composed_of_phase2_primitives(kernel: KernelContainer) -> None:
    """A colon word built from Phase 2 primitives runs through DOCOL/EXIT: DIFF = SWAP -."""
    machine = kernel.machine()
    emulator = machine.emulator()

    image = kernel.kernel_builder().build(
        colon_words=[ColonWordDto(name='DIFF', words=('SWAP', '-'))],
        boot=boot_thread('LIT', 3, 'LIT', 10, 'DIFF', 'BYE'),
    )
    boot(emulator, image)
    emulator.run()

    assert machine.data_stack().pop() == 7  # noqa: PLR2004 -- 10 - 3 (SWAP reverses the operands)


@pytest.mark.unit
def test_colon_using_the_return_stack_leaves_it_balanced(kernel: KernelContainer) -> None:
    """`: PASS >R R> ;` round-trips a value and leaves the return stack balanced."""
    machine = kernel.machine()
    emulator = machine.emulator()
    return_stack = machine.return_stack()

    image = kernel.kernel_builder().build(
        colon_words=[ColonWordDto(name='PASS', words=('>R', 'R>'))],
        boot=boot_thread('LIT', 9, 'PASS', 'BYE'),
    )
    boot(emulator, image)
    emulator.run()

    assert machine.data_stack().pop() == 9  # noqa: PLR2004 -- the value survived >R R>
    assert return_stack.pointer == return_stack.base


@pytest.mark.unit
def test_boot_thread_maps_names_to_references_and_ints_to_literals() -> None:
    """The ergonomic factory turns a str/int mix into the ThreadItemDto union."""
    assert boot_thread('LIT', 3, 'BYE') == (
        WordReferenceDto('LIT'),
        LiteralCellDto(Cell(3)),
        WordReferenceDto('BYE'),
    )


@pytest.mark.unit
def test_boot_loads_the_program_and_points_ip_at_the_boot_thread(kernel: KernelContainer) -> None:
    """The boot() helper: load the image and set IP -- ready to run from START."""
    machine = kernel.machine()
    emulator = machine.emulator()
    image = kernel.kernel_builder().build(colon_words=[], boot=boot_thread('BYE'))

    boot(emulator, image)

    assert emulator.pc == 0  # run starts at START (program index 0)
    assert emulator.registers.read(Register.IP) == image.boot_ip

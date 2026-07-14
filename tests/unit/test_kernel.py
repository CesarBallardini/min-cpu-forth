"""Unit tests for the Phase 1 ITC kernel: real threaded execution through NEXT/DOCOL/EXIT."""

import pytest

from min_cpu_forth import layout
from min_cpu_forth.adapters.memory import ListMemoryAdapter
from min_cpu_forth.containers import KernelContainer
from min_cpu_forth.domain.dtos import AssemblyDto, ColonWordDto
from min_cpu_forth.domain.register import Register
from min_cpu_forth.domain.types import Address, ProgramIndex
from min_cpu_forth.errors import KernelError
from min_cpu_forth.services.kernel.builder import KernelBuilder, boot_thread


class _StartMisplacedAssembler:
    """An ``AssemblerPort`` stub whose ``START`` label is not at program index 0."""

    def assemble(self, source: str) -> AssemblyDto:
        del source
        return AssemblyDto(program=(), labels={'START': ProgramIndex(5), 'ENTER': ProgramIndex(1)})


@pytest.fixture
def kernel() -> KernelContainer:
    """A fresh kernel container (its own machine + assembler) per test."""
    return KernelContainer()


@pytest.mark.unit
def test_square_runs_end_to_end_through_real_next(kernel: KernelContainer) -> None:
    """3 SQUARE -> 9 threaded through LIT/DOCOL/DUP/*/EXIT/BYE -- the first true ITC execution.

    Every earlier version executed a colon definition by iterating a Python list of word names;
    this drives the real ``NEXT`` double-indirection over a dictionary laid out in ``cpu.mem``.
    """
    builder = kernel.kernel_builder()
    machine = kernel.machine()
    emulator = machine.emulator()
    data_stack = machine.data_stack()

    image = builder.build(
        colon_words=[ColonWordDto(name='SQUARE', words=('DUP', '*'))],
        boot=boot_thread('LIT', 3, 'SQUARE', 'BYE'),
    )
    emulator.load(image.program)
    emulator.registers.write(Register.IP, image.boot_ip)
    emulator.run()

    assert data_stack.pop() == 9


@pytest.mark.unit
def test_code_word_header_is_laid_out_as_specified(kernel: KernelContainer) -> None:
    """The first CODE word's header matches the docs/03 format, and its CFA is the code-field cell."""
    builder = kernel.kernel_builder()
    memory = kernel.machine().memory()

    image = builder.build(colon_words=[], boot=boot_thread('BYE'))

    base = layout.DICTIONARY_BASE  # LIT is installed first, so its header starts here
    assert memory.read(Address(base + 0)) == 0  # link: first word -> 0
    assert memory.read(Address(base + 1)) == 0  # immediate flag
    assert memory.read(Address(base + 2)) == 0  # smudge flag
    assert memory.read(Address(base + 3)) == len('LIT')  # name length
    assert [memory.read(Address(base + 4 + n)) for n in range(3)] == [ord(ch) for ch in 'LIT']
    assert image.word_cfas['LIT'] == base + 4 + len('LIT')  # the code-field cell


@pytest.mark.unit
def test_colon_thread_holds_cfas_terminated_by_exit(kernel: KernelContainer) -> None:
    """A colon word's parameter field is a thread of the referenced CFAs, ending in EXIT's CFA."""
    builder = kernel.kernel_builder()
    memory = kernel.machine().memory()

    image = builder.build(
        colon_words=[ColonWordDto(name='SQUARE', words=('DUP', '*'))],
        boot=boot_thread('BYE'),
    )

    cfa = image.word_cfas['SQUARE']
    thread = [memory.read(Address(cfa + 1)), memory.read(Address(cfa + 2)), memory.read(Address(cfa + 3))]
    assert thread == [image.word_cfas['DUP'], image.word_cfas['*'], image.word_cfas['EXIT']]


@pytest.mark.unit
def test_nested_colon_definitions_execute_and_balance_the_return_stack(
    kernel: KernelContainer,
) -> None:
    """A colon word calling another colon word nests DOCOL/EXIT; the return stack ends balanced."""
    builder = kernel.kernel_builder()
    machine = kernel.machine()
    emulator = machine.emulator()
    data_stack = machine.data_stack()
    return_stack = machine.return_stack()

    image = builder.build(
        colon_words=[
            ColonWordDto(name='SQUARE', words=('DUP', '*')),
            ColonWordDto(name='FOURTH', words=('SQUARE', 'SQUARE')),  # calls SQUARE, defined above
        ],
        boot=boot_thread('LIT', 2, 'FOURTH', 'BYE'),
    )
    emulator.load(image.program)
    emulator.registers.write(Register.IP, image.boot_ip)
    emulator.run()

    assert data_stack.pop() == 16  # noqa: PLR2004 -- ((2^2)^2)
    assert return_stack.pointer == return_stack.base  # every ENTER matched by an EXIT


@pytest.mark.unit
def test_two_literals_multiplied_directly_at_the_top_level(kernel: KernelContainer) -> None:
    """LIT twice then ``*`` -- exercises LIT and a CODE word without any colon indirection."""
    builder = kernel.kernel_builder()
    machine = kernel.machine()
    emulator = machine.emulator()

    image = builder.build(colon_words=[], boot=boot_thread('LIT', 5, 'LIT', 3, '*', 'BYE'))
    emulator.load(image.program)
    emulator.registers.write(Register.IP, image.boot_ip)
    emulator.run()

    assert machine.data_stack().pop() == 15  # noqa: PLR2004 -- 5 * 3


@pytest.mark.unit
def test_latest_link_chain_walks_installed_words_in_reverse(kernel: KernelContainer) -> None:
    """The link-before-name chain from LATEST visits every word, newest first -- Phase 4's FIND."""
    builder = kernel.kernel_builder()
    memory = kernel.machine().memory()

    builder.build(colon_words=[], boot=boot_thread('BYE'))

    names: list[str] = []
    name_field = memory.read(layout.LATEST_ADDR)
    while name_field != 0:
        length = memory.read(Address(name_field))
        names.append(''.join(chr(memory.read(Address(name_field + 1 + n))) for n in range(length)))
        name_field = memory.read(Address(name_field - 3))  # link cell precedes immediate/smudge/len
    assert names == ['BYE', '*', 'DUP', 'EXIT', 'LIT']  # reverse of install order


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
    """The boot guard: ``START`` must assemble at program index 0 (``EmulatorService.run`` starts there)."""
    builder = KernelBuilder(assembler=_StartMisplacedAssembler(), memory=ListMemoryAdapter(layout.MEMORY_SIZE))

    with pytest.raises(KernelError, match='START'):
        builder.build(colon_words=[], boot=boot_thread('BYE'))

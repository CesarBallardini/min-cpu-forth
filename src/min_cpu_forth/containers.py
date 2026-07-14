"""Dependency-injection wiring: the one place adapters are bound to ports.

Every module outside this one depends on abstractions; here each port is bound to a concrete
adapter and the services are composed. Instantiating a container yields a fresh, isolated
machine -- the singletons are per-container instance, so a new container per test gets clean
memory and stacks.
"""

from dependency_injector import containers, providers

from min_cpu_forth.adapters.dictionary import MemoryDictionaryAdapter
from min_cpu_forth.adapters.io import (
    BufferCharacterOutputAdapter,
    QueueCharacterInputAdapter,
)
from min_cpu_forth.adapters.memory import ListMemoryAdapter
from min_cpu_forth.adapters.registers import DictRegisterFileAdapter
from min_cpu_forth.adapters.stack import DownwardStackAdapter
from min_cpu_forth.adapters.system_variables import MemorySystemVariablesAdapter
from min_cpu_forth.layout import (
    DATA_STACK_BASE,
    DATA_STACK_SIZE,
    MEMORY_SIZE,
    RETURN_STACK_BASE,
    RETURN_STACK_SIZE,
)
from min_cpu_forth.services.assembler.emitter import InstructionEmitter
from min_cpu_forth.services.assembler.parser import LineParser
from min_cpu_forth.services.assembler.resolver import LabelAddressResolver
from min_cpu_forth.services.assembler.service import TextAssembler
from min_cpu_forth.services.emulator import EmulatorService
from min_cpu_forth.services.forth import ForthService
from min_cpu_forth.services.kernel.builder import KernelBuilder


class MachineContainer(containers.DeclarativeContainer):
    """Wires the shared data path, the opcode emulator, and the Forth interpreter."""

    memory = providers.Singleton(ListMemoryAdapter, size=MEMORY_SIZE)
    data_stack = providers.Singleton(DownwardStackAdapter, memory=memory, base=DATA_STACK_BASE, size=DATA_STACK_SIZE)
    return_stack = providers.Singleton(
        DownwardStackAdapter, memory=memory, base=RETURN_STACK_BASE, size=RETURN_STACK_SIZE
    )
    emulator_registers = providers.Singleton(DictRegisterFileAdapter)
    forth_registers = providers.Singleton(DictRegisterFileAdapter)
    char_input = providers.Singleton(QueueCharacterInputAdapter)
    char_output = providers.Singleton(BufferCharacterOutputAdapter)

    emulator = providers.Factory(
        EmulatorService,
        registers=emulator_registers,
        memory=memory,
        data_stack=data_stack,
        return_stack=return_stack,
        char_input=char_input,
        char_output=char_output,
    )
    forth = providers.Factory(
        ForthService,
        data_stack=data_stack,
        return_stack=return_stack,
        memory=memory,
        registers=forth_registers,
    )


class AssemblerContainer(containers.DeclarativeContainer):
    """Wires the three assembler stages into the assembler use case."""

    parser = providers.Factory(LineParser)
    resolver = providers.Factory(LabelAddressResolver)
    emitter = providers.Factory(InstructionEmitter)
    assembler = providers.Factory(TextAssembler, parser=parser, resolver=resolver, emitter=emitter)


class KernelContainer(containers.DeclarativeContainer):
    """Composes a machine and an assembler so the kernel builder shares the machine's memory.

    ``machine`` is a nested `MachineContainer`: the emulator built from it and the kernel builder
    below both resolve the *same* memory singleton, so the dictionary the builder writes is the
    one the emulator runs against.
    """

    machine = providers.Container(MachineContainer)
    assembler_stages = providers.Container(AssemblerContainer)

    system_variables = providers.Singleton(MemorySystemVariablesAdapter, memory=machine.memory)
    dictionary = providers.Singleton(MemoryDictionaryAdapter, memory=machine.memory, system_variables=system_variables)

    kernel_builder = providers.Factory(
        KernelBuilder,
        assembler=assembler_stages.assembler,
        dictionary=dictionary,
    )

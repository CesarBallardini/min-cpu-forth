"""The ``cpu.mem`` memory map (see ``docs/03-assembler-plan.md`` "Memory layout").

The data and return stacks occupy non-overlapping regions at the top of memory; the dictionary,
system variables, and text buffers share the block below them. These constants are the single
source of truth the dependency-injection container wires the memory and stack adapters from.
"""

CELL_SIZE = 1
DICTIONARY_SIZE = 2048
DATA_STACK_SIZE = 1024
RETURN_STACK_SIZE = 1024

DATA_STACK_BASE = DICTIONARY_SIZE + DATA_STACK_SIZE
RETURN_STACK_BASE = DATA_STACK_BASE + RETURN_STACK_SIZE
MEMORY_SIZE = RETURN_STACK_BASE

"""The ``cpu.mem`` memory map (see ``docs/03-assembler-plan.md`` "Memory layout").

The data and return stacks occupy non-overlapping regions at the top of memory; the dictionary,
system variables, and text buffers share the block below them. These constants are the single
source of truth the dependency-injection container wires the memory and stack adapters from.
"""

from min_cpu_forth.domain.types import Address

CELL_SIZE = 1
DICTIONARY_SIZE = 2048
DATA_STACK_SIZE = 1024
RETURN_STACK_SIZE = 1024

DATA_STACK_BASE = Address(DICTIONARY_SIZE + DATA_STACK_SIZE)
RETURN_STACK_BASE = Address(DATA_STACK_BASE + RETURN_STACK_SIZE)
MEMORY_SIZE: int = RETURN_STACK_BASE

# The system-variables + dictionary block occupies the lowest `DICTIONARY_SIZE` cells (below the
# data stack, whose floor is `DATA_STACK_BASE - DATA_STACK_SIZE`). System variables sit at fixed
# addresses at the bottom; the dictionary grows upward from `DICTIONARY_BASE`, with `DP` (HERE)
# tracking its top and `LATEST` linking the most recently defined word. Phase 1 needs only DP and
# LATEST; the rest of the reserved block leaves room for STATE / >IN / 'SOURCE / BASE (Phase 5).
SYSTEM_VARS_BASE = Address(0)
DP_ADDR = Address(SYSTEM_VARS_BASE + 0)
LATEST_ADDR = Address(SYSTEM_VARS_BASE + 1)
SYSTEM_VARS_SIZE = 8
DICTIONARY_BASE = Address(SYSTEM_VARS_BASE + SYSTEM_VARS_SIZE)
DICTIONARY_TOP = Address(DICTIONARY_SIZE)  # exclusive upper bound; equals the data-stack floor

# A fixed scratch buffer near the top of the dictionary block where WORD builds its counted string
# (Phase 4). It sits well above the small kernel dictionary; a real growable dictionary would place
# it after DP with a bounds check, but the kernel's word set is fixed and tiny.
WORD_BUFFER_SIZE = 64
WORD_BUFFER_BASE = Address(DICTIONARY_SIZE - WORD_BUFFER_SIZE)

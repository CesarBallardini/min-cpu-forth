"""Semantic scalar types that distinguish the machine's two address spaces.

The Harvard split (``docs/03-assembler-plan.md``) is the design's central subtlety: a cell address
in ``cpu.mem`` (data space), an index into ``EmulatorService.program`` (code space), and a value
stored in a cell are three different things that all happen to be integers. These ``NewType``s make
the distinction nominal, so the type checker flags a program index used where an address belongs --
exactly the category error the design keeps warning about. They are zero-cost at runtime.
"""

from typing import NewType

# A position in cpu.mem (data space) -- a cell address.
Address = NewType('Address', int)

# A position in EmulatorService.program (code space) -- a native routine entry / label target.
ProgramIndex = NewType('ProgramIndex', int)

# The content of a cpu.mem cell.
Cell = NewType('Cell', int)

"""The reserved machine registers, as a ``StrEnum`` to replace magic string literals.

``RegisterFilePort`` stays keyed by ``str`` -- the assembler emits arbitrary register names from
source -- but the *reserved* registers the threading core and interpreter rely on get named here.
Because ``StrEnum`` members are ``str``, ``Register.IP`` is a valid argument wherever a register
name is expected, so hand-written Python references the enum while the port stays open.

The kernel assembly (``services/kernel/routines.py``) uses these same names as text; keep the two
in sync.
"""

from enum import StrEnum


class Register(StrEnum):
    """The registers reserved by the ITC core and the Forth interpreter."""

    IP = 'IP'  # interpreter pointer (also the Forth model's thread pointer)
    W = 'W'  # the current word's Code Field Address
    XT = 'XT'  # the code-field value currently being jumped to
    NEXT_POINTER = 'NEXTREG'  # holds NEXT's program index, set once at START

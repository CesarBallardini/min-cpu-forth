"""The ITC threading core and the CODE-word primitive set, as assembler source.

These routines are true Indirect Threaded Code (`docs/03-assembler-plan.md`): a word's Code Field
holds a *pointer*, never a synthesized ``CALL``. Reconciled with the Harvard split of the machine
(`services/emulator.py` runs a `program`; `LOAD`/`STORE`/stacks address `cpu.mem`):

- A **thread** is a run of cells in ``cpu.mem``, each holding a **CFA** -- the ``cpu.mem`` address
  of a word's code-field cell. ``IP`` indexes the thread.
- A **code-field cell** holds a **``program`` index** (a native routine's entry point).
- ``NEXT`` does the double indirection ``W := mem[IP]`` (a CFA) then ``XT := mem[W]`` (a program
  index) and ``JMP XT`` -- a jump in *code* space. ``W`` ends holding the **CFA**, the convention
  ``EXECUTE``/``DODOES`` must share (moving3).

Register discipline: ``IP`` (interpreter pointer), ``W`` (current word's CFA), ``XT`` (code-field
value being jumped to), and ``NEXTREG`` (holds ``NEXT``'s program index, set once at ``START``)
are reserved; primitives touch only scratch registers (``X``/``Y``/``Z``/``ACC``/``Q``/``R``).
Every primitive ends ``JMP NEXTREG`` rather than returning -- that is what makes this threaded
code. ``START`` is deliberately first so it sits at ``program`` index 0, where ``EmulatorService``
begins.

The core routines (``START``/``NEXT``/``ENTER``) are not dictionary words. Every dictionary word
is a ``KernelPrimitive`` -- a ``CodeWordDto`` paired with its routine source -- so the full program
and the ``CODE_WORDS`` list are both derived from one ``PRIMITIVES`` table (Phase 2).
"""

from typing import NamedTuple

from min_cpu_forth.domain.dtos import CodeWordDto

# Label of the shared colon-entry routine (a colon word's code-field value is this routine's
# program index). Not itself a dictionary word.
ENTER_LABEL = 'ENTER'

# START must assemble at program index 0; NEXT/ENTER follow. None of these are dictionary words.
CORE_SOURCE = """
START:
        SET  NEXTREG, NEXT   ; hold NEXT's program index for the whole run
        JMP  NEXTREG

NEXT:
        LOAD W, IP           ; W := mem[IP]        (W = CFA)
        ADD  IP, 1           ; advance the thread pointer (CELL = 1)
        LOAD XT, W           ; XT := mem[W]        (code-field value = program index)
        JMP  XT              ; tail-jump into the primitive

ENTER:
        PUSH_R IP            ; save the caller's IP
        ADD  W, 1            ; W := CFA + 1 = parameter-field address
        MOV  IP, W           ; IP := parameter field
        JMP  NEXTREG
"""


class KernelPrimitive(NamedTuple):
    """A CODE word paired with the assembler source of its native routine."""

    word: CodeWordDto
    source: str


def _primitive(name: str, label: str, source: str) -> KernelPrimitive:
    """Build a ``KernelPrimitive`` whose routine is labelled ``label`` in ``source``."""
    return KernelPrimitive(word=CodeWordDto(name=name, routine_label=label), source=source)


# Every dictionary word. `LIT`/`EXIT` are here because threads reference them by CFA (an inline
# literal / every colon thread's terminator), alongside the visible primitives. `C@`/`C!` alias
# `@`/`!` -- the cell-addressed model has no sub-cell byte layer.
PRIMITIVES: tuple[KernelPrimitive, ...] = (
    _primitive(
        'LIT',
        'LIT',
        """
LIT:
        LOAD ACC, IP         ; ACC := the inline literal (cell after LIT's CFA in the thread)
        PUSH_D ACC
        ADD  IP, 1           ; step IP past the literal cell
        JMP  NEXTREG
""",
    ),
    _primitive(
        'EXIT',
        'EXIT',
        """
EXIT:
        POP_R IP             ; restore the caller's IP
        JMP  NEXTREG
""",
    ),
    _primitive(
        'BYE',
        'BYE',
        """
BYE:
        HALT
""",
    ),
    # --- Stack ops ---
    _primitive(
        'DUP',
        'DUP',
        """
DUP:
        POP_D X              ; ( a -- a a )
        PUSH_D X
        PUSH_D X
        JMP  NEXTREG
""",
    ),
    _primitive(
        'DROP',
        'DROP',
        """
DROP:
        POP_D X              ; ( a -- )
        JMP  NEXTREG
""",
    ),
    _primitive(
        'SWAP',
        'SWAP',
        """
SWAP:
        POP_D X              ; ( a b -- b a )
        POP_D Y
        PUSH_D X
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        'OVER',
        'OVER',
        """
OVER:
        POP_D X              ; ( a b -- a b a )
        POP_D Y
        PUSH_D Y
        PUSH_D X
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        'ROT',
        'ROT',
        """
ROT:
        POP_D X              ; ( a b c -- b c a )
        POP_D Y
        POP_D Z
        PUSH_D Y
        PUSH_D X
        PUSH_D Z
        JMP  NEXTREG
""",
    ),
    _primitive(
        '-ROT',
        'NROT',
        """
NROT:
        POP_D X              ; ( a b c -- c a b )
        POP_D Y
        POP_D Z
        PUSH_D X
        PUSH_D Z
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        'NIP',
        'NIP',
        """
NIP:
        POP_D X              ; ( a b -- b )
        POP_D Y
        PUSH_D X
        JMP  NEXTREG
""",
    ),
    _primitive(
        'TUCK',
        'TUCK',
        """
TUCK:
        POP_D X              ; ( a b -- b a b )
        POP_D Y
        PUSH_D X
        PUSH_D Y
        PUSH_D X
        JMP  NEXTREG
""",
    ),
    # --- Arithmetic ---
    _primitive(
        '+',
        'PLUS',
        """
PLUS:
        POP_D X              ; ( a b -- a+b )
        POP_D Y
        ADD  Y, X
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        '-',
        'MINUS',
        """
MINUS:
        POP_D X              ; ( a b -- a-b )
        POP_D Y
        SUB  Y, X
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        '*',
        'MUL',
        """
MUL:
        POP_D X              ; ( a b -- a*b )  multiply by repeated addition
        POP_D Y
        SUB  ACC, ACC        ; ACC := 0
MUL_LOOP:
        JZ   X, MUL_DONE
        ADD  ACC, Y
        SUB  X, 1
        SET  R, MUL_LOOP
        JMP  R
MUL_DONE:
        PUSH_D ACC
        JMP  NEXTREG
""",
    ),
    _primitive(
        'NEGATE',
        'NEGATE',
        """
NEGATE:
        POP_D X              ; ( a -- -a )
        SUB  Y, Y
        SUB  Y, X
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        'ABS',
        'ABS',
        """
ABS:
        POP_D X              ; ( a -- |a| )
        JS   X, ABS_NEG
        PUSH_D X
        JMP  NEXTREG
ABS_NEG:
        SUB  Y, Y
        SUB  Y, X
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        '1+',
        'ONEPLUS',
        """
ONEPLUS:
        POP_D X              ; ( a -- a+1 )
        ADD  X, 1
        PUSH_D X
        JMP  NEXTREG
""",
    ),
    _primitive(
        '1-',
        'ONEMINUS',
        """
ONEMINUS:
        POP_D X              ; ( a -- a-1 )
        SUB  X, 1
        PUSH_D X
        JMP  NEXTREG
""",
    ),
    # --- Memory ops (C@/C! alias @/!) ---
    _primitive(
        '@',
        'FETCH',
        """
FETCH:
        POP_D X              ; ( addr -- mem[addr] )
        LOAD Y, X
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        '!',
        'STOREW',
        """
STOREW:
        POP_D X              ; ( val addr -- )  addr on top
        POP_D Y
        STORE X, Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        'C@',
        'CFETCH',
        """
CFETCH:
        POP_D X              ; ( addr -- mem[addr] )  aliases @ in a cell-addressed model
        LOAD Y, X
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        'C!',
        'CSTOREW',
        """
CSTOREW:
        POP_D X              ; ( val addr -- )  aliases !
        POP_D Y
        STORE X, Y
        JMP  NEXTREG
""",
    ),
    # --- Return stack ---
    _primitive(
        '>R',
        'TOR',
        """
TOR:
        POP_D X              ; ( a -- ) ( R: -- a )
        PUSH_R X
        JMP  NEXTREG
""",
    ),
    _primitive(
        'R>',
        'FROMR',
        """
FROMR:
        POP_R X              ; ( R: a -- ) ( -- a )
        PUSH_D X
        JMP  NEXTREG
""",
    ),
    _primitive(
        'R@',
        'RFETCH',
        """
RFETCH:
        POP_R X              ; ( R: a -- a ) ( -- a )
        PUSH_R X
        PUSH_D X
        JMP  NEXTREG
""",
    ),
    # --- Comparison / logic (flags are 1 = true, 0 = false) ---
    _primitive(
        '=',
        'EQUALS',
        """
EQUALS:
        POP_D X              ; ( a b -- flag )
        POP_D Y
        SUB  Y, X
        JZ   Y, EQ_TRUE
        SET  Z, 0
        PUSH_D Z
        JMP  NEXTREG
EQ_TRUE:
        SET  Z, 1
        PUSH_D Z
        JMP  NEXTREG
""",
    ),
    _primitive(
        '<>',
        'NOTEQUALS',
        """
NOTEQUALS:
        POP_D X              ; ( a b -- flag )
        POP_D Y
        SUB  Y, X
        JZ   Y, NE_FALSE
        SET  Z, 1
        PUSH_D Z
        JMP  NEXTREG
NE_FALSE:
        SET  Z, 0
        PUSH_D Z
        JMP  NEXTREG
""",
    ),
    _primitive(
        '<',
        'LESSTHAN',
        """
LESSTHAN:
        POP_D X              ; ( a b -- a<b )  a-b < 0  (cells are unbounded ints -- no overflow)
        POP_D Y
        SUB  Y, X
        JS   Y, LT_TRUE
        SET  Z, 0
        PUSH_D Z
        JMP  NEXTREG
LT_TRUE:
        SET  Z, 1
        PUSH_D Z
        JMP  NEXTREG
""",
    ),
    _primitive(
        '>',
        'GREATERTHAN',
        """
GREATERTHAN:
        POP_D X              ; ( a b -- a>b )  b-a < 0
        POP_D Y
        SUB  X, Y
        JS   X, GT_TRUE
        SET  Z, 0
        PUSH_D Z
        JMP  NEXTREG
GT_TRUE:
        SET  Z, 1
        PUSH_D Z
        JMP  NEXTREG
""",
    ),
    _primitive(
        '0=',
        'ZEROEQ',
        """
ZEROEQ:
        POP_D X              ; ( a -- a==0 )
        JZ   X, ZE_TRUE
        SET  Z, 0
        PUSH_D Z
        JMP  NEXTREG
ZE_TRUE:
        SET  Z, 1
        PUSH_D Z
        JMP  NEXTREG
""",
    ),
    _primitive(
        '0<',
        'ZEROLT',
        """
ZEROLT:
        POP_D X              ; ( a -- a<0 )
        JS   X, ZL_TRUE
        SET  Z, 0
        PUSH_D Z
        JMP  NEXTREG
ZL_TRUE:
        SET  Z, 1
        PUSH_D Z
        JMP  NEXTREG
""",
    ),
    _primitive(
        'AND',
        'BITAND',
        """
BITAND:
        POP_D X              ; ( a b -- a&b )
        POP_D Y
        AND  Y, X
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        'OR',
        'BITOR',
        """
BITOR:
        POP_D X              ; ( a b -- a|b )
        POP_D Y
        OR   Y, X
        PUSH_D Y
        JMP  NEXTREG
""",
    ),
    _primitive(
        'INVERT',
        'BITINVERT',
        """
BITINVERT:
        POP_D X              ; ( a -- ~a )
        INVERT X
        PUSH_D X
        JMP  NEXTREG
""",
    ),
)

KERNEL_SOURCE = CORE_SOURCE + ''.join(primitive.source for primitive in PRIMITIVES)
CODE_WORDS: tuple[CodeWordDto, ...] = tuple(primitive.word for primitive in PRIMITIVES)

"""The ITC threading core as assembler source, plus the CODE-word catalog it defines.

These routines are true Indirect Threaded Code (`docs/03-assembler-plan.md`): a word's Code Field
holds a *pointer*, never a synthesized ``CALL``. Reconciled with the Harvard split of the machine
(`services/emulator.py` runs a `program`; `LOAD`/`STORE`/stacks address `cpu.mem`):

- A **thread** is a run of cells in ``cpu.mem``, each holding a **CFA** -- the ``cpu.mem`` address
  of a word's code-field cell. ``IP`` indexes the thread.
- A **code-field cell** holds a **``program`` index** (a native routine's entry point).
- ``NEXT`` does the double indirection ``W := mem[IP]`` (a CFA) then ``XT := mem[W]`` (a program
  index) and ``JMP XT`` -- a jump in *code* space. So ``W`` ends holding the **CFA**, the
  convention ``EXECUTE``/``DODOES`` must share (moving3).

Register discipline: ``IP`` (interpreter pointer), ``W`` (current word's CFA), ``XT`` (code-field
value being jumped to), and ``NEXTREG`` (holds ``NEXT``'s program index, set once at ``START``)
are reserved. Primitives may only touch scratch registers (``X``/``Y``/``ACC``/``R``); clobbering
a reserved register corrupts the running thread. Every primitive ends ``JMP NEXTREG`` rather than
returning -- that is what makes this threaded code. ``START`` is deliberately first so it sits at
``program`` index 0, where ``EmulatorService.run`` begins.
"""

from min_cpu_forth.domain.dtos import CodeWordDto

# Label of the shared colon-entry routine (a colon word's code-field value is this routine's
# program index). Not itself a dictionary word.
ENTER_LABEL = 'ENTER'

KERNEL_SOURCE = """
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

EXIT:
        POP_R IP             ; restore the caller's IP
        JMP  NEXTREG

LIT:
        LOAD ACC, IP         ; ACC := the inline literal (the cell after LIT's CFA in the thread)
        PUSH_D ACC
        ADD  IP, 1           ; step IP past the literal cell
        JMP  NEXTREG

DUP:
        POP_D X              ; ( a -- a a )
        PUSH_D X
        PUSH_D X
        JMP  NEXTREG

MUL:
        POP_D X              ; ( a b -- a*b )  X = b (counter), Y = a; multiply by repeated add
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

BYE:
        HALT
"""

# The CODE words this kernel installs into the dictionary: name -> the routine label above.
# `LIT` and `EXIT` are here because threads reference them by CFA (an inline literal / the
# terminator of every colon thread), just like the visible primitives `DUP`, `*`, and `BYE`.
CODE_WORDS: tuple[CodeWordDto, ...] = (
    CodeWordDto(name='LIT', routine_label='LIT'),
    CodeWordDto(name='EXIT', routine_label='EXIT'),
    CodeWordDto(name='DUP', routine_label='DUP'),
    CodeWordDto(name='*', routine_label='MUL'),
    CodeWordDto(name='BYE', routine_label='BYE'),
)

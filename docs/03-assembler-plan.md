# A phased plan for an ITC Forth in assembler

`docs/01-first-steps.md` traced the original design conversation and found its biggest gap: no
prototype, ever, actually threaded a real colon definition through `DOCOL`/`NEXT`, had a real
dictionary, or could read Forth source text. `docs/02-cpu-design.md` closed the ISA half of that
gap (a reconciled opcode catalog) and `src/min_cpu_forth`'s `EmulatorService` closed the
execution half (a real fetch-decode-execute loop). Nothing yet *runs Forth* on top of either.
This document is the plan for that: a phased build-out, each phase landing its own tests before
the next phase starts, informed by Brad Rodriguez's "Moving Forth" series and his CamelForth
reference kernel.

This is mostly a plan, not a record of what's built -- same posture as `docs/02-cpu-design.md`.
The one exception: **Phase 0 (the assembler) is now implemented** (see its section below); Phases
1+ (the ITC kernel) are not. Remaining phases get implemented one at a time, each against this
document.

> **Naming note.** This document was written against an earlier flat layout and still refers to
> `Emulator`/`Instruction`/`emulator.py` and `min_cpu_forth.cpu`. The code has since been
> restructured into a hexagonal (ports-and-adapters) architecture, so those map to:
> `Emulator` → `services/emulator.py`'s `EmulatorService`; `Instruction` → `domain/dtos.py`'s
> `InstructionDto`; the `program`/`pc` fields → `EmulatorService.load(program)` and its `pc`
> property; `cpu.mem` and the stack bases → the `MemoryPort`/`StackPort` adapters wired by
> `MachineContainer`, with the layout constants (`DATA_STACK_BASE`, ...) in `layout.py`. The
> design reasoning below is unchanged; only the module/class names moved.

## Sources, and what we take from each

- **[Moving Forth: Part 1](https://www.bradrodriguez.com/papers/moving1.htm)** (already the
  basis of `docs/design/prompt-1.md`): classical Indirect Threaded Code. `NEXT` fetches through
  `IP` to get a word's Code Field Address, fetches again through the Code Field to get a native
  routine address, and jumps there -- a double indirection. `DOCOL`/`ENTER` pushes the caller's
  `IP` and re-enters `NEXT` inside the new word's Parameter Field; `EXIT` pops it back.
- **[Part 2](https://www.bradrodriguez.com/papers/moving2.htm)**: a benchmarking study across the
  6809, 8051, Z80, and 8086, comparing ITC against Direct-Threaded Code (DTC, code field *is* the
  jump target) and Subroutine-Threaded Code (STC, code field is a hardware `CALL`). The load-
  bearing lesson: **which registers are "pointer-capable" decides which threading model a CPU can
  support** -- the 8051 gets forced into STC because it has exactly one usable address register
  (DPTR). Our CPU has general-purpose named registers, not a register-starved special-purpose
  set, so ITC (your explicit choice) is a natural fit rather than something we're fighting the
  hardware for. The article also surfaces a **Harvard-architecture gotcha** (no way to write to
  program memory) for the 8051 -- directly relevant below, because our `Emulator` turns out to be
  Harvard-architecture-shaped too (see "Memory layout").
- **[Part 3](https://www.bradrodriguez.com/papers/moving3.htm)**, "Demystifying DOES>": opens by
  fixing a bug in Part 2's own 6809 design -- `EXECUTE` broke because `NEXT` didn't leave the
  executed word's address in a register in the convention `DODOES` expected. The rule that fixes
  it, stated as a hard invariant: **whatever convention `NEXT` uses for where the "current word"
  pointer ends up (Code Field Address vs Parameter Field Address, in a register or not), `EXECUTE`
  and `DODOES` must use that exact same convention.** This is the single most important thing to
  keep self-consistent across Phases 1, 4, and 7. The article also formalizes the Code
  Field/Parameter Field split, and notes it's an **ITC-specific artifact**: "the machine code
  could be started at the Code Field, and continued into the Parameter Field" for DTC/STC, but for
  ITC "the Code Field must contain the address of the machine code to be executed. So the machine
  code is placed in the Parameter Field, and the Code Field contains the address of the Parameter
  Field." (Our own version of this needs one adjustment -- see "Dictionary header format" below.)
- **[Part 6](https://www.bradrodriguez.com/papers/moving6.htm)**: one concrete memory map
  (Z80/CamelForth under CP/M) and one dictionary-header comparison across four Forths
  (CamelForth, Fig-Forth, Pygmy Forth, F83). Two load-bearing facts we're reusing: the memory
  map's region list (dictionary, a fixed-size user-area block of system variables, parameter
  stack, `HOLD`/`PAD` buffers, return stack), and Charles Curley's finding, cited in the article,
  that **the compiler is measurably faster when the link field comes before the name** rather than
  after (as fig-Forth did it).
- **[CamelForth for Z80](https://www.bradrodriguez.com/papers/camel80.txt)**
  (`camel80.txt`/`camel80h.txt`/`camel80d.txt`): a complete, working reference kernel. Important
  correction the research surfaced: **CamelForth is Direct-Threaded, not Indirect-Threaded** --
  its code field holds a `CALL` instruction, not a pointer. Since we're building ITC, we take
  CamelForth's *organization, word list, dictionary-search algorithm, compiler algorithm, and
  control-structure compilation* as the reference, but re-derive every `NEXT`/`ENTER`/`EXIT`/
  `DODOES` routine for true ITC rather than porting its DTC code-field trick verbatim.

## Decisions locked in

1. **Build a minimal text/label assembler first** (Phase 0). Hand-computing branch offsets -- and
   hand-poking jump-target registers, the way `tests/unit/test_emulator.py`'s
   `*`-via-repeated-addition test currently does -- doesn't scale to a real kernel; the assembler
   must resolve labels into *both* signed branch offsets and absolute jump targets so a program is
   self-contained in its own text (see Phase 0 for the `SET` pseudo-op that makes `JMP <label>`
   work without adding an opcode).
2. **Curated core word list**: stack/arithmetic/memory/logic/control primitives (from
   `docs/02-cpu-design.md`), the outer interpreter (`WORD`/`FIND`/`NUMBER`/`INTERPRET`/`QUIT`),
   the colon compiler, control structures (`IF/THEN`, `BEGIN/UNTIL`, `DO/LOOP`), and
   `CREATE`/`DOES>`. Deferred: double-cell arithmetic, `UM*`/`UM/MOD`, pictured numeric output
   (`#`, `<#`, `#>`, `HOLD`), and CP/M-specific words -- see "Explicitly deferred" below.
3. **`IN`/`OUT` opcodes**, added to the ISA in the same change that introduced this document (see
   `docs/02-cpu-design.md`'s "New: I/O" section) -- `KEY`/`EMIT` need somewhere to read from and
   write to that no combination of the other 15 opcodes can reach.
4. **CamelForth-derived dictionary header** -- adapted below for a cell-addressed machine rather
   than copied byte-for-byte, since CamelForth's bit-packing is a byte-economy hack for an 8-bit
   target we don't need.

## Memory layout

Our `Emulator` is architecturally Harvard: `Emulator.pc` indexes `Emulator.program`
(a `list[Instruction]`, the *code* space), while `LOAD`/`STORE`/the stacks all address
`cpu.mem` (a `list[int]`, the *data* space) via `min_cpu_forth.cpu.CPU`. These are two separate
Python lists -- an address in one means nothing in the other. This is exactly the gotcha Part 2
flags for the 8051 ("there is physically no means to write to the program memory"), except here
it's a deliberate simplification rather than a hardware limitation to route around: **a CODE
word's Code Field Address is a `program` index; every other dictionary field lives in and is
addressed within `cpu.mem`.** `JMP`/`JZ`/`JS` all operate on `Emulator.pc`, so a CFA read out of
`cpu.mem` via `LOAD` is just an integer until something puts it in a register and `JMP`s to it --
which works fine, but means (unlike a single-address-space real CPU) a CFA cell can't be
dereferenced with `LOAD` to "see" the instructions it points to. Keep this distinction in mind
through Phase 1.

Within `cpu.mem`, following moving6's region list (adapted -- we have no OS, no CP/M-reserved
zero page, and no fixed load address, so those CP/M-specific regions are dropped):

```
low addresses
+------------------------+
| System variables       |   fixed cells: DP, LATEST, STATE, >IN, 'SOURCE (2 cells), BASE
+------------------------+
| Dictionary space        |   grows upward; DP (a.k.a. HERE) tracks the top
|  (headers + colon       |
|   threads + CODE words' |
|   dictionary entries)   |
~~~~~~~~~~~~~~~~~~~~~~~~~~~
| PAD buffer               |   scratch text buffer, fixed size, tracks just above dictionary growth
+------------------------+
| Terminal Input Buffer    |   fixed size, holds one line of input at a time
+------------------------+
| Data stack               |   already exists: min_cpu_forth.cpu.DATA_STACK_BASE, grows down
+------------------------+
| Return stack              |  already exists: min_cpu_forth.cpu.RETURN_STACK_BASE, grows down
+------------------------+
high addresses
```

`min_cpu_forth.cpu.CPU` already reserves `DICTIONARY_SIZE = 2048` cells below the data stack for
exactly the "system variables + dictionary + PAD + TIB" block above -- Phase 1 subdivides that
existing region rather than changing `cpu.py`'s stack layout. Exact fixed-cell offsets (which
system variable lives at which address) get pinned down when Phase 1 actually starts, not in
this document -- the region *order* is the design decision worth locking in now.

## Dictionary header format

Adapted from moving6's Figure 2 (CamelForth's header) and moving3's Code Field/Parameter Field
split, for a cell-addressed machine with separate code/data address spaces:

| Field | Size | Contents |
| --- | --- | --- |
| Link | 1 cell | Address (in `cpu.mem`) of the **previous word's Name field** -- link-before-name, per Curley's finding cited in moving6. |
| Immediate flag | 1 cell | Nonzero if this word runs at compile time even while compiling (`IF`, `THEN`, `;`, ...). Kept as its own cell rather than a packed bit -- we're not fighting for bytes the way an 8-bit target is. |
| Smudge flag | 1 cell | Nonzero while a definition is mid-compile (hides it from `FIND` so it can't be accidentally self-referenced -- `RECURSE` bypasses this deliberately, per `camel80h.txt`). |
| Name length | 1 cell | Character count of the name that follows. |
| Name | *n* cells | One cell per character (no packing -- unlike CamelForth's counted-string-in-bytes, our cells are Python ints, so each character is just its ordinal value in its own cell). |
| Code field (CFA) | 1 cell | **CODE words**: a `program` index -- the entry point of this word's assembled routine (see "Memory layout" above; this is not a `cpu.mem` address). **Colon words**: the `program` index of the single shared `ENTER` routine. |
| Parameter field (PFA) | variable | **Colon words only**: a thread -- a list of cells, each holding another word's CFA, terminated by `EXIT`'s CFA. **CODE words don't have a meaningful parameter field** in our model: unlike a real single-address-space CPU (where, per moving3, "the machine code is placed in the Parameter Field"), a CODE word's actual instructions live in `Emulator.program`, a separate space `cpu.mem` can't address into. This is the one place our design deliberately diverges from moving3's literal description, for the Harvard-architecture reason above. |

`NEXT`/`EXECUTE`/`DODOES` all agree on the convention: **`W` (the word register) ends up holding
the word's Code Field Address**, not its Parameter Field Address -- the simpler of the two options
moving3 discusses, and the one that keeps `EXECUTE` (`POP_D W; LOAD XT,[W]; JMP XT` -- read the
CFA, dereference it, jump) trivially consistent with `NEXT` itself. Whoever implements Phase 1
should re-read moving3's "colossal mistake" section before writing `EXECUTE`, precisely because
it's easy to get this backwards.

## The phases

Each phase names what it builds, what it reuses from the previous phase, and what its tests
prove that the previous phase's tests didn't. File paths are named where the shape is obvious now
(e.g. Phase 0's assembler); phases past that name a likely module but the exact name gets fixed
when that phase starts.

### Phase 0 -- Minimal assembler  ✅ built

**Status:** implemented as the `src/min_cpu_forth/services/assembler/` pipeline -- `parser.py`
(`LineParser`) → `resolver.py` (`LabelAddressResolver`) → `emitter.py` (`InstructionEmitter`),
orchestrated by `service.py`'s `TextAssembler` and wired via `AssemblerContainer`; the static
operand table lives in `specs.py`. Covered by `tests/unit/test_assembler.py`. The rest of this
section is the design it was built to; where it says `Instruction` read `InstructionDto` and
where it says a single `assembler.py` read the pipeline above (see the naming note at the top).

**Builds on:** `domain/opcode.py`'s `Opcode` and `domain/dtos.py`'s `InstructionDto`.

**Why it comes first, and why it's more than "remove hand-counting":** the two hand-built
programs in `tests/unit/test_emulator.py` only run because the *test harness* reaches in and
pokes the one address a `JMP` needs (`emulator.registers['LOOP_ADDR'] = 3` in the `*` test). A
real kernel has no harness. Phase 1's every primitive ends with a jump to `NEXT`, and `NEXT`
lives at some fixed `program` index the primitive itself must get into a register before it can
`JMP` there. So Phase 0's real job is to make a program *self-contained in its own text* -- every
address it needs, jump targets included, resolved from labels at assemble time rather than
injected from outside. Landing that capability here is what stops Phase 1 from having to extend
the assembler mid-flight.

**What gets built:** a text-to-`InstructionDto` assembler (delivered as the
`services/assembler/` pipeline described under **Status** above).

- *Line-oriented source.* One instruction, label definition, comment, or blank line per line. A
  label definition is `name:` (on its own line or preceding an instruction); a comment runs from
  `;` to end of line. Opcode mnemonics are the 17 `Opcode` names verbatim (uppercase); register
  names are case-sensitive identifiers -- exactly the arbitrary string keys `Emulator.registers`
  already uses.

- *Operand shapes come straight from the emulator's per-opcode table* (the docstring table in
  `emulator.py`): the assembler encodes that table as its single source of truth for which field
  (`a`, `b`, `offset`) each operand lands in, and whether `b` is a register or an immediate. A
  bare integer literal is an immediate (`int`); a bare identifier is a register (`str`) -- the
  same `str`-vs-`int` distinction `_resolve` keys on at runtime.

- *A label resolves differently by position -- the one sharp edge to document loudly:*
  - In a `JZ`/`JS` **offset** slot it resolves to a **signed relative offset**,
    `target_index - (branch_index + 1)`, because `step()` advances `PC` past the branch *before*
    the handler adds the offset (the `*` test's `JZ ... offset=3` at index 3 landing at index 7
    is exactly `7 - (3 + 1)`). Backward branches therefore assemble to *negative* offsets; the
    assembler must handle both directions, even though the current hand-built `*` sidesteps
    backward branching by using a register `JMP`.
  - In an `ADD`/`SUB`/`AND`/`OR`/`SET` **immediate** slot it resolves to its **absolute
    `program` index**.
  The same token means a relative distance in one place and an absolute address in another; the
  assembler picks by operand position, and the tests should assert this so nobody reads a label
  as "an address" uniformly.

- *`JMP`-to-a-label, without a new opcode.* The ISA has no load-immediate, so the only way to get
  a label's absolute address into a register is `SUB r, r` (zero it) then `ADD r, <label>` -- then
  `JMP r`. The assembler offers this as one convenience pseudo-instruction, `SET r, <label-or-int>`,
  that expands to exactly those two real `Instruction`s. `SET` is assemble-time sugar, **not** a
  new opcode -- it emits only ops already in the canonical set, so the ISA invariant in `CLAUDE.md`
  holds. With it, a self-contained backward loop is `SET R, LOOP` / `JMP R`, and a forward
  primitive tail is `SET R, NEXT` / `JMP R`.

- *Output.* `assemble(source)` returns both the `list[Instruction]` (a drop-in for
  `Emulator(cpu, program)`) and the resolved label-to-index symbol table -- Phase 1's CODE-word
  installer needs a routine's entry index to write into its Code Field, so the symbol table is a
  first-class return value, not a debugging afterthought. Multiple labeled routines assemble into
  one program with cross-references resolved across the whole unit (so `DUP` can name `NEXT` even
  though `NEXT` is defined elsewhere in the same source). This whole-program resolution -- not the
  two-program regression below -- is the capability Phase 1 actually depends on.

**Tests** (`tests/unit/test_assembler.py`):
- *`DUP` round-trips structurally.* It has no jumps, so its assembled `list[Instruction]` must
  compare **equal** (frozen-dataclass `==`) to the hand-built list in `test_emulator.py` -- the
  strongest possible "safe drop-in" proof.
- *`*` proves label-to-`JMP` materialization behaviorally.* Rewritten to resolve its backward
  branch from a label (`SET LOOP_ADDR, LOOP` / `JMP LOOP_ADDR`) instead of a harness-poked
  register, its assembled list is deliberately *not* identical to the hand-built one (it now
  carries the `SUB`/`ADD` expansion), so this case asserts **behavioral** equivalence: assemble,
  `run()`, and check the data stack yields `42` with no external register poking. The two cases
  together cover both assertion modes and both label roles (relative offset vs absolute address).
- *A signed backward `JZ`/`JS` offset* assembles to the correct negative number -- the direction
  the hand-built programs never exercise.
- *Error cases raise clearly:* unknown mnemonic, reference to an undefined label, a duplicate
  label definition, and wrong operand count/shape for an opcode. Each is a small assertion that
  the assembler fails loudly rather than emitting a subtly wrong `Instruction`.

### Phase 1 -- ITC threading core over a real dictionary

**Builds on:** Phase 0's assembler; the memory layout and header format above.

**What gets built:** the header format laid out in `cpu.mem`; `NEXT`, `DOCOL`/`ENTER`, `EXIT`,
`LIT` assembled per `docs/design/instruction-set.md`'s canonical routines, using true ITC (code
field is a pointer, never a synthesized `CALL`); a small "install a CODE word" helper (writes a
header, points its CFA at an already-assembled routine's `program` index) and "install a colon
word" helper (writes a header, CFA = `ENTER`'s index, PFA = a thread of other words' CFAs
terminated by `EXIT`'s CFA).

**Tests:** build a dictionary containing just `NEXT`/`ENTER`/`EXIT`/`LIT` plus `DUP` and `*` as
CODE words (reusing their existing assembled logic from `docs/02-cpu-design.md`'s worked
examples), thread a `SQUARE` colon word referencing their CFAs, and run it through `NEXT` for
real. **This is the first time `DOCOL`/`EXIT` are ever exercised end to end** -- every prior
version, per `docs/01-first-steps.md`, executed colon definitions by iterating a Python list of
word names instead.

### Phase 2 -- Core primitive word set

**Builds on:** Phase 1's CODE-word installer and header format.

**What gets built:** every CODE word from the curated list -- stack (`DUP DROP SWAP OVER ROT
-ROT NIP TUCK`), arithmetic (`+ - * / MOD NEGATE ABS 1+ 1-`), memory (`@ ! C@ C!`), return stack
(`>R R> R@`), comparison/logic (`= <> < > 0= 0< AND OR INVERT`) -- assembled per
`docs/02-cpu-design.md`'s worked examples and installed with real headers.

**Tests:** one threaded program per word (or logical group) asserting stack effects through the
real dictionary and `NEXT`, mirroring Phase 1's `SQUARE` test but covering the full word list.

### Phase 3 -- Branching and loop runtime

**Builds on:** Phase 2's primitives (specifically `SUB`/`JS`/`JZ` at the opcode level, already
proven in Phase 1/2's tests).

**What gets built:** `BRANCH`/`0BRANCH` as CODE words; `(do)`/`(loop)`/`(+loop)`/`I`/`J`/`UNLOOP`
as the `DO`-loop runtime, using plain index/limit comparison (`SUB` then `JS`) rather than
CamelForth's 16-bit-overflow "fudge factor" trick (`8000h - limit`) -- that trick exists purely to
make loop termination detectable via signed-overflow on a *fixed-width* register, and our cells
are unbounded Python ints, so there's no overflow to detect and no reason to port the cleverness.

**Tests:** hand-threaded (not yet compiler-generated -- that's Phase 6) programs exercising these
runtime words directly, e.g. a manually-threaded countdown loop using `(do)`/`(loop)`/`I`.

### Phase 4 -- I/O words and dictionary search

**Builds on:** the `IN`/`OUT` opcodes; Phase 1's header format (specifically the link-before-name
chain `FIND` walks).

**What gets built:** `KEY`/`EMIT` as thin CODE wrappers over `IN`/`OUT`; `WORD` (tokenizer --
skip leading delimiters, scan to next delimiter, build a counted result); `FIND` (walk the
`LATEST`-rooted link chain, compare names, return the CFA plus an immediate/normal flag, per
`camel80h.txt`'s algorithm); `NUMBER`/`?NUMBER` (ASCII-to-integer, with an optional leading `-`).

**Tests:** seed `Emulator.input_queue` with a canned line's character codes, drive
`WORD`+`FIND`+`NUMBER` directly (no compiler loop yet) and assert correct tokenization,
dictionary lookup, and numeric parsing.

### Phase 5 -- The interpreter loop and colon compiler

**Builds on:** Phase 4's `WORD`/`FIND`/`NUMBER`; Phase 1's dictionary-installer helpers,
generalized into real Forth words.

**What gets built:** `HERE`/`ALLOT`/`,`/`C,` (dictionary growth); `STATE`; `:`/`;` (the colon
compiler -- `CREATE` a header, then rewrite its code field from a placeholder to `ENTER`,
adapted from `camel80h.txt`'s `!COLON`/`,EXIT` pattern for a true-ITC code field rather than a
`CALL`-based one); `INTERPRET` (find-or-number-or-error loop); `QUIT` (the REPL: read a line via
`KEY` into the Terminal Input Buffer, `INTERPRET` it, report errors via `EMIT`, repeat).

**Tests:** feed `": SQUARE DUP * ; 3 SQUARE"` character-by-character through `input_queue`, run
`QUIT`, and assert the resulting data stack and `output`. **This is the first true end-to-end
"type Forth source, get a result" test** -- `docs/01-first-steps.md` flagged that "there is
currently no way to feed this interpreter Forth source text"; this phase is what removes that
sentence's truth.

### Phase 6 -- Structured control-flow compiler words

**Builds on:** Phase 3's `BRANCH`/`0BRANCH`; Phase 5's colon compiler and `HERE`.

**What gets built:** `IF/ELSE/THEN`, `BEGIN/UNTIL/WHILE/REPEAT`, `DO/LOOP/+LOOP/LEAVE` as
`IMMEDIATE` colon words that compile `0BRANCH`/`BRANCH` with backpatched addresses left on the
data stack at compile time -- following `camel80h.txt`'s algorithms (e.g. `IF` compiles
`0BRANCH` plus a placeholder cell and leaves that placeholder's address on the stack; `THEN`
patches it to the current `HERE`). This finally replaces the `lambda: None` stubs
`build_standard_colon_defs` has carried in `src/min_cpu_forth/forth.py` since the `-3.py`
prototype, per `docs/01-first-steps.md`.

**Tests:** real Forth source through `QUIT` exercising `IF/ELSE/THEN`, a `BEGIN/UNTIL` loop, and
a `DO/LOOP` with `I`, asserting runtime results end to end.

### Phase 7 (optional / stretch) -- `CREATE`/`DOES>`

**Builds on:** Phase 5's `CREATE`-adjacent header-writing code; the `NEXT`/`W`-convention
established in Phase 1.

**What gets built:** `DODOES`, re-derived for ITC using moving3's corrected register-discipline
rule (the same "`W` ends at CFA" convention `EXECUTE` already relies on, from Phase 1); `CREATE`;
`DOES>`.

**Tests:** define a simple `CREATE ... DOES>` word (e.g. a basic constant-defining word) and
verify its runtime behavior matches a plain `CONSTANT`.

## Explicitly deferred

Kept out of the curated core (decision 2 above), in case a later phase needs to revisit the
scope call:

- Double-cell arithmetic (`2@ 2! 2DUP 2SWAP 2OVER`, `M*`, `SM/REM`, `FM/MOD`) and the unsigned
  multiply/divide primitives (`UM*`, `UM/MOD`) they're built on.
- Pictured numeric output (`<# # #S #> HOLD SIGN .` and friends).
- `U<`/`U>` (unsigned comparison) -- `docs/02-cpu-design.md` already flagged `JS` only tests a
  signed sign bit, so unsigned ordering needs a different primitive if it's ever added.
- CP/M-specific words (`BDOS`, `CPMACCEPT`, `BYE`'s `jp 0`) -- meaningless without a host OS;
  `BYE` in our design is just `HALT`.
- Vocabularies/wordlists and hashed dictionary search -- CamelForth itself uses "the simplest
  scheme: a single linked list," which is also what Phase 4 builds; multiple wordlists are a
  possible future extension, not a gap in the curated core.

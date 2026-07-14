# First steps: how the design conversation shaped this codebase

This document exists for reviewers. It walks through `docs/design/` and `docs/prototypes/`
in the order they were produced, explains what changed at each step, and calls out where the
design and the code disagree with each other or with themselves. Read it before proposing
changes to `src/min_cpu_forth/` -- several of its simplifications are deliberate responses to
problems that showed up during this history, not oversights.

The whole exploration happened as a single conversation with ChatGPT-4, seeded with an excerpt
from Brad Rodriguez's article
["Moving Forth: Part 1 -- The Threading Technique"](https://www.bradrodriguez.com/papers/moving1.htm).
Each design doc is that conversation's next reply; each prototype script is a follow-up attempt
to make the design executable. Four things evolved together and at different paces: the CPU's
instruction set, the assembler/object-code layout for that CPU, the Forth primitives built on
top of it, and the Python code meant to run all of it. They didn't stay in sync, and that
mismatch is the main thing worth understanding before touching the code.

## Stage 1: the seed article (`docs/design/prompt-1.md`)

The prompt quotes Rodriguez's explanation of classical Indirect Threaded Code (ITC): a Forth
"thread" is a list of Code Field Addresses; `NEXT` fetches through `IP` to get a word's CFA,
fetches again through that CFA to get the native routine address, and jumps to it (a double
indirection). Colon definitions have `DOCOL` as their code field: it pushes the caller's `IP`,
sets `IP` to the word's Parameter Field, and re-enters `NEXT`. `EXIT` (compiled from `;`) pops
`IP` back and re-enters `NEXT`. The request built on top of this: define a minimal virtual CPU
-- registers, memory map, instruction set -- capable of running this execution model.

## Stage 2: a broad first draft (`docs/design/response-1.md`)

The first response is deliberately generous, not minimal. It proposes seven registers (`IP`,
`W`, `XT`, `DSP`, `RSP`, `PC`, and an optional cached-TOS register `T`), a memory map with
separate dictionary/data-stack/return-stack regions, the classic header/code-field/parameter-field
word layout, and a wide instruction set: `NEXT`, `DOCOL`, `EXIT`, `DODOES` (for `CREATE`/`DOES>`),
`LIT`, `BRANCH`/`0BRANCH`, a full stack-manipulation group, ALU and logic ops, memory ops, and
`PCALL`/`RET`/`TRAP`/`HALT`. It explicitly flags that only `IP`, `W`, `DSP`, `RSP` are strictly
necessary for ITC -- everything else is there for efficiency, not because ITC requires it. That
distinction between "necessary" and "convenient" is what the next stage acts on.

## Stage 3: narrowing to an actual minimal instruction set (`docs/design/instruction-set.md`)

This is the canonical ISA reference for the whole project: the design converges on ten
operations -- `LOAD`, `STORE`, `ADD`, `JMP`, `JZ`, `PUSH_D`, `POP_D`, `PUSH_R`, `POP_R`, `HALT` --
and shows `NEXT`, `DOCOL`, `EXIT`, `LIT`, and `0BRANCH` written strictly in terms of them. There's
no dedicated `MOV`; the doc shows how to synthesize one with a `PUSH_D`/`POP_D` round-trip rather
than adding an eleventh opcode. Everything else in Forth -- `DUP`, `+`, `@`, and so on -- is meant
to be microcode built from these ten ops, not new CPU instructions. This file is the contract the
rest of the design is supposed to honor. As the next stage shows, it doesn't always.

## Stage 4: microcoding the core primitives (`minimal-itc-forth-primitives-{1,2}.md`)

Two near-duplicate passes (file 2 mostly repeats file 1 with the same content reorganized) write
`DUP`, `DROP`, `SWAP`, `OVER`, `+`, `-`, `*`, `/`, `@`, `!`, `LIT`, `DOCOL`, `EXIT`, `0BRANCH`,
and `BRANCH` as short instruction sequences over the ten-op ISA -- for example:

```asm
; DUP
POP_D X
PUSH_D X
PUSH_D X
JMP NEXT
```

These two files are the high-water mark of ISA discipline in the whole design conversation:
every routine shown is genuinely expressible in `LOAD`/`STORE`/`ADD`/`JMP`/`JZ`/`PUSH_D`/`POP_D`/
`PUSH_R`/`POP_R`. That discipline slips almost immediately afterward.

## Stage 5: filling out the word set -- and drifting from the ISA (`minimal-itc-forth-primitives-3.md`)

This pass adds `ROT`, `-ROT`, `NIP`, `TUCK`, `MOD`, `NEGATE`, `ABS`, `1+`, `1-`, `C@`/`C!`,
`>R`/`R>`/`R@`, comparisons, and logic ops. Several of these routines quietly invent instructions
that were never added to the ISA: `SUB`, `MUL`, `DIV`, `NEG`, `CMP`, `JL`, `JG`, `AND`, `OR`,
`NOT` all appear here as if they were primitive opcodes, e.g.:

```asm
; <
POP_D X
POP_D Y
CMP Y, X      ; set flags
JL TRUE
...
```

`instruction-set.md` has no `CMP`, no condition flags, and no `JL`/`JG` -- only `JZ`. This is the
first and clearest case of the instruction-set.md contract being broken rather than honored: a
reviewer reading this file as a literal spec would conclude the minimal ISA needs at least a
comparison unit and a handful of arithmetic opcodes it was explicitly designed not to have. Read
these routines as *aspirational pseudocode for a slightly richer CPU*, not as valid microcode
for the ten-op machine defined in stage 3.

## Stage 6: structured control words (`minimal-itc-forth-primitives-{4,5}.md`)

Two passes at `IF`/`ELSE`/`THEN`, `BEGIN`/`UNTIL`, `WHILE`/`REPEAT`, `DO`/`LOOP`/`+LOOP`, and
`EXIT`. Both explain the *compilation strategy* clearly -- `IF` compiles a `0BRANCH` placeholder,
`THEN` patches it, loop words juggle index/limit on the return stack -- but neither one produces
runnable code. The Forth-level sketches are placeholders standing in for a compiler that doesn't
exist yet:

```forth
: IF   0BRANCH ;        \ compile-time: emit 0BRANCH with placeholder
: ELSE BRANCH ;          \ compile-time: patch previous IF, emit BRANCH placeholder
: THEN ;                 \ compile-time: patch previous 0BRANCH / BRANCH
```

`0BRANCH`/`BRANCH` as compiled by these definitions never actually get an offset, and nothing in
the conversation ever writes the compiler that would patch one in. This is the largest unfinished
piece of the whole design: two dedicated passes were spent on it, and none of it made it into
working code at any later stage.

## Stage 7: a self-hosted outer interpreter (`minimal-itc-forth-primitives-6.md`)

The most ambitious document: it sketches a `NEXT` *outer* interpreter (the REPL, not the inner
threading loop of the same name) written in Forth itself, using `WORD`, `FIND`, `NUMBER?`, and
`EXECUTE`. None of those four words are defined anywhere in `docs/design/` or implemented in any
prototype -- they're referenced as if they already existed. Treat this file as a sketch of a
future direction, not as something any current code implements or should be assumed to support.

## Stage 8: four Python prototypes (`docs/prototypes/assembler-interpreter-{1..4}.py`)

This is where the design meets executable code, and where the biggest gap between the two
appears: **none of the four scripts emulate the byte-level CPU from stages 3-5.** There's no
opcode stream, no fetch/decode/execute cycle over `LOAD`/`STORE`/`ADD`/`JMP`/`JZ`. Instead, every
script models Forth at the *semantic* level -- Python closures that directly manipulate Python
list-backed stacks. `NEXT`, `DOCOL`, and `EXIT` end up as Python method calls, not micro-op
sequences. That's a reasonable simplification for prototyping word semantics quickly, but it
means the microcode in stages 3-6 was never actually validated by running it.

- **`-1.py`** is the closest attempt at the real thing: a `CPU`/`Stack`/`Instruction` class
  hierarchy (`LOAD`, `STORE`, `ADD`, `JMP`, `JZ` are all objects with an `execute(cpu)` method,
  matching the strategy-pattern style of the ISA docs) plus a `ForthVM` with a dictionary,
  `add_colon_def`, and a `run_word` inner-interpreter loop. But `DOCOL` is faked
  (`vm.dictionary["DOCOL"] = -2`) rather than wired to a real code field, and `run_word`'s
  termination check (`if self.cpu.IP == 0: break`) is fragile -- it treats address zero as an
  implicit end-of-thread sentinel that nothing else in the design establishes. This script is
  never referenced again by later stages; it's a dead end, not a foundation.

- **`-2.py`** abandons the opcode-level model entirely. `CPU` becomes a plain object with named
  attributes (`ip`, `w`, `dsp`, `rsp`), and `ForthExecutioner` installs each Forth word as a
  lambda closing over `self.cpu`. This is the shape that `-3.py` and `-4.py` build on, and it's
  also where a real bug enters: `Stack(self.mem, self.dsp)` and `Stack(self.mem, self.rsp)` are
  both constructed with `self.dsp == self.rsp == MEMORY_SIZE` -- the data stack and return stack
  start at the *same* address in the *same* backing list. The demo in this file only ever touches
  the data stack, so the collision is never triggered and never noticed.

- **`-3.py`** re-declares `ForthExecutioner` from scratch to add `add_colon_def`/`_execute_colon`
  and placeholder colon definitions for `IF_THEN`, `BEGIN_UNTIL`, and friends (all `lambda: None`
  -- stubs, not implementations of stage 6's design). It's a copy-paste-and-extend of `-2.py`
  rather than an import or a diff, so it isn't runnable on its own (`CPU`, `Dict`, `List`, and
  `Callable` are all undefined in this file in isolation).

- **`-4.py`** merges `-2.py` and `-3.py` into one consistent, runnable file. It's the most
  complete prototype and the one `src/min_cpu_forth/` was consolidated from -- including the
  stack-collision bug, which survived unnoticed through this final merge too.

## What a reviewer should take away from this history

- **The ISA in `instruction-set.md` and the code in `src/min_cpu_forth/` operate at different
  levels of abstraction, on purpose.** The design docs specify a byte-level microcoded CPU; the
  code implements Forth word *semantics* directly in Python. That gap was never closed anywhere
  in this conversation, so don't read `cpu.py`/`forth.py` as an implementation of
  `instruction-set.md`'s opcode stream -- it isn't one, and closing that gap (an actual
  fetch/decode/execute loop over compiled threads) is still open work.
- **`DOCOL`/`EXIT` were never exercised end-to-end.** Every "run a colon definition" demo, from
  `-2.py` through the current `tests/unit/test_forth.py`, executes `SQUARE` by iterating a Python
  list of word names (`_execute_colon`), not by entering `DOCOL` and letting `NEXT` walk a
  compiled thread. The `DOCOL`/`EXIT` primitives exist and are unit-tested in isolation
  (`test_docol_and_exit_round_trip_through_return_stack`), but nothing yet drives them from real
  execution.
- **The stack-collision bug is the cautionary tale of this whole history.** It was introduced in
  `-2.py`, survived `-3.py` and `-4.py`, and was only caught when `src/min_cpu_forth/cpu.py` was
  ported and a test was written that actually exercises both stacks together
  (`test_data_and_return_stacks_do_not_collide`). The lesson generalizes: any feature this design
  conversation didn't demo, it also didn't validate.
- **Colon definitions can't use `LIT` or `DOCOL`.** Both are installed as one-argument callables
  (`lambda n: ...`, `lambda addr: ...`), but `_execute_colon` invokes every word in a definition
  with zero arguments. In practice, a colon definition can only chain together zero-arity
  primitives (as `SQUARE`'s `['DUP', '*']` does) -- it can't push a literal or explicitly enter
  another colon definition. This has been true since `-2.py` and is still true in
  `src/min_cpu_forth/forth.py`.
- **Structured control words never left the stub stage.** Two design docs (stage 6) worked out
  the compilation strategy for `IF`/`ELSE`/`THEN` and the loop words, but no script -- prototype
  or current -- implements `0BRANCH`/`BRANCH` with a real, resolved offset. `build_standard_colon_defs`
  in `src/min_cpu_forth/forth.py` still installs the same `lambda: None` stubs it inherited from
  `-3.py`.
- **The outer interpreter (tokenizer/REPL) doesn't exist.** Stage 7's `WORD`/`FIND`/`NUMBER?`/
  `EXECUTE` sketch was never implemented; `-1.py`'s `repl()` (split on whitespace, look up in a
  dict) is the only attempt at one anywhere in this history, and it was dropped starting with
  `-2.py`. There is currently no way to feed this interpreter Forth source text -- only to build
  colon definitions and drive primitives programmatically from Python.

## Where this leaves things

`src/min_cpu_forth/` is a faithful, tested port of `-4.py`'s semantic model, with the
stack-collision bug fixed and the `DROP` primitive corrected to a properly-typed helper (see
`CLAUDE.md`'s "Design invariants" section). It is *not* an implementation of the byte-level ISA
from `docs/design/instruction-set.md`, it does not run colon definitions through `DOCOL`/`NEXT`,
it has no branching or looping, and it has no source-text reader. Any of those would be a
legitimate next step; none of them should be assumed to already work.

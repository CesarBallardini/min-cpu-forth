# CPU design: the opcode set for a minimal Forth

This is a plan, not a record of what's built. [`docs/01-first-steps.md`](01-first-steps.md)
found that the original design conversation never settled on one CPU: `docs/design/instruction-set.md`
declares a nine-op core (ten counting `HALT`), then the microcode passes in
`minimal-itc-forth-primitives-3.md` quietly invent `SUB`, `MUL`, `DIV`, `NEG`, `CMP`, `JL`, `JG`,
`AND`, `OR`, and `NOT` to cover arithmetic, comparisons, and logic -- none of which were ever
added to the declared instruction set. No prototype ever emulated any of this at the opcode
level, so the conflict was never forced to resolve. This document resolves it: one opcode
catalog, everything in it justified, sized to actually run the "minimal Forth" word list the
design conversation settled on (`docs/design/minimal-itc-forth-primitives-2.md`'s and
`-3.md`'s summary tables).

## Goals

- **Keep the core exactly as designed.** `docs/design/instruction-set.md`'s ten operations
  (`LOAD`, `STORE`, `ADD`, `JMP`, `JZ`, `PUSH_D`, `POP_D`, `PUSH_R`, `POP_R`, `HALT`) are
  untouched. They're sufficient for `NEXT`, `DOCOL`, `EXIT`, `LIT`, and `0BRANCH`, and nothing
  here should threaten that.
- **Add only what's provably not synthesizable from the core.** Every new opcode below comes
  with the argument for why it can't be built out of what already exists -- not just a
  restatement of "it's convenient."
- **Resolve every op stage 5 invented, without necessarily adopting it.** `SUB`, `MUL`, `DIV`,
  `NEG`, `CMP`, `JL`, `JG`, `AND`, `OR`, `NOT` each get either kept (justified), replaced with a
  smaller equivalent, or shown to be unnecessary because the core (plus whatever this document
  does add) can already synthesize it.
- **Keep the branch model uniform.** `0BRANCH` already needs a way to test a popped flag and
  branch. Comparisons should produce a flag *value* Forth can push, test, and combine --
  not a second family of conditional jumps parallel to `JZ`.

## The fix that removes most of the drift: operand forms, not new opcodes

Read literally, `docs/design/instruction-set.md` defines `ADD r, imm` -- register plus a
compile-time constant. But its own routines don't stay inside that limit: `NEXT`/`DOCOL`/`LIT`
use `ADD IP, CELL` (immediate, to advance a pointer), while every primitives doc's `+` uses
`ADD Y, X` (register plus register, to add two values popped at runtime). Nobody ever declared
that second form -- it's just been assumed since stage 4. This document makes it explicit rather
than leaving it implicit:

> **`ADD dst, src`: `src` may be an immediate constant or a register.** The assembler picks the
> encoding; the semantics are identical either way -- `dst := dst + src`.

`SUB` (added below) gets the same rule. This one clarification is why the catalog below needs
far fewer new opcodes than stage 5 accumulated: most of what stage 5 reached for a new mnemonic
to solve, a register-or-immediate `ADD`/`SUB` already covers.

## The opcode catalog

### Core (unchanged, 10 opcodes)

| Opcode | Operands | Semantics |
| --- | --- | --- |
| `LOAD` | `r, [r]` | `r := mem[r]` |
| `STORE` | `[r], r2` | `mem[r] := r2` |
| `ADD` | `r, src` | `r := r + src` (`src`: immediate or register) |
| `JMP` | `r` | `PC := r` |
| `JZ` | `r, offset` | if `r == 0`: `PC := PC + offset` |
| `PUSH_D` | `r` | `DSP := DSP - CELL; mem[DSP] := r` |
| `POP_D` | `r` | `r := mem[DSP]; DSP := DSP + CELL` |
| `PUSH_R` | `r` | `RSP := RSP - CELL; mem[RSP] := r` |
| `POP_R` | `r` | `r := mem[RSP]; RSP := RSP + CELL` |
| `HALT` | -- | stop |

### New: arithmetic and a second conditional branch (2 opcodes)

| Opcode | Operands | Semantics | Why it's necessary |
| --- | --- | --- | --- |
| `SUB` | `r, src` | `r := r - src` (`src`: immediate or register) | `ADD` alone can't subtract two *runtime* values -- there's no way to negate a register's contents with only immediate addition. `SUB r, r` also zeroes a register, which turns out to be the key building block for several idioms below. |
| `JS` | `r, offset` | if `r < 0` (sign bit set): `PC := PC + offset` | `JZ` only tests for zero. Ordering comparisons (`<`, `>`, `0<`) need to test a sign, and there are no condition-code flags in this ISA to test after the fact. `JS` is `JZ`'s exact sibling -- same shape, same cost -- and it's the *only* new conditional branch needed. It replaces stage 5's `CMP`/`JL`/`JG` (three inventions) with one. |

### New: bitwise logic (3 opcodes)

| Opcode | Operands | Semantics | Why it's necessary |
| --- | --- | --- | --- |
| `AND` | `r, src` | `r := r & src` | Bitwise AND has no arithmetic construction from `ADD`/`SUB`/branches over an unbounded word width. Needed directly by the `AND` word, and indirectly by anything that does address alignment or flag masking. |
| `OR` | `r, src` | `r := r \| src` | Same argument as `AND`. Needed directly by the `OR` word. |
| `INVERT` | `r` | `r := ~r` (bitwise complement) | Same argument; unary. Needed directly by the `INVERT` word. |

**Total: 15 opcodes** -- the 10-op core, plus `SUB` and `JS`, plus `AND`/`OR`/`INVERT`. That's 5
additions in place of stage 5's 10 unreconciled ones, and every one of the 5 has a specific word
or idiom below that can't be built without it.

### What did *not* make the cut, and why

| Stage-5 invention | Verdict | Reason |
| --- | --- | --- |
| `MUL`, `DIV` | Not added | Synthesizable as loops over `SUB`/`JS`/`JZ`/`JMP` (shown below). O(n) in operand magnitude instead of O(1), which is the honest cost of staying minimal -- consistent with `instruction-set.md`'s own "absolute minimum" framing. |
| `NEG` | Not added | `SUB r, r` (zero) followed by `SUB r, x` gives `-x` for free once `SUB` exists; a dedicated negate opcode would be redundant. |
| `CMP`, `JL`, `JG` | Not added (replaced by `JS`) | Flags-based comparison is a bigger machine (a flags register, multiple conditional jumps reading it) for the same result `JS` gets with one opcode and no new state. |
| `NOT` | Renamed, not added | This is `INVERT` under a different name in the same doc set -- one opcode, not two. |

## Synthesizing everything else from the 15 opcodes

### Loading a small immediate into a register

The core has no `MOV`/`LOADI`. Zero a register with self-subtraction, then add the constant:

```asm
SUB X, X      ; X := 0
ADD X, 5      ; X := 5
```

### Copying a register (`MOV`, revisited)

`docs/design/instruction-set.md` synthesizes `MOV` with a data-stack round-trip
(`PUSH_D W; POP_D IP`). With `SUB`/`ADD` now supporting register operands, there's a cheaper
form that doesn't touch the data stack at all:

```asm
SUB IP, IP    ; IP := 0
ADD IP, W     ; IP := 0 + W = W
```

### `NEGATE` and `ABS`

```asm
; NEGATE ( n -- -n )
POP_D X
SUB Y, Y      ; Y := 0
SUB Y, X      ; Y := 0 - X = -X
PUSH_D Y
JMP NEXT

; ABS ( n -- |n| )  -- NEGATE only if negative
POP_D X
JS X, DO_NEGATE
PUSH_D X
JMP NEXT
DO_NEGATE:
SUB Y, Y
SUB Y, X
PUSH_D Y
JMP NEXT
```

### Comparisons produce a value, not a jump

Every comparison word pops its operand(s), computes a flag with `SUB`+`JZ`/`JS`, and *pushes*
the Forth-standard boolean (`0` / `-1`, or `0` / `1` -- pick one convention project-wide) rather
than branching around Forth-level code. This keeps `0BRANCH` the only place a comparison result
ever turns into control flow, matching how Forth itself works (`IF` consumes a stack value; it
doesn't know the operation that produced it).

```asm
; 0= ( n -- flag )
POP_D X
JZ X, TRUE
SUB Y, Y        ; Y := 0  (false)
PUSH_D Y
JMP NEXT
TRUE:
SUB Y, Y
ADD Y, 1        ; Y := 1  (true)
PUSH_D Y
JMP NEXT

; 0< ( n -- flag )   same shape, JS instead of JZ
POP_D X
JS X, TRUE
SUB Y, Y
PUSH_D Y
JMP NEXT
TRUE:
SUB Y, Y
ADD Y, 1
PUSH_D Y
JMP NEXT

; = ( a b -- flag )       SUB then 0=
; <> ( a b -- flag )      SUB then 0=, with TRUE/FALSE branches swapped
; < ( a b -- flag )       SUB (a-b) then 0<
; > ( a b -- flag )       SUB (b-a) then 0<   -- i.e. swap operands, reuse <
```

### `*` (multiplication) -- repeated addition

```asm
; * ( a b -- a*b ), b >= 0
POP_D X        ; X := b (counter)
POP_D Y        ; Y := a
SUB ACC, ACC   ; ACC := 0
LOOP:
JZ X, DONE
ADD ACC, Y
SUB X, 1
JMP LOOP
DONE:
PUSH_D ACC
JMP NEXT
```

### `/` and `MOD` -- repeated subtraction

```asm
; /MOD ( a b -- rem quot ), a >= 0, b > 0
POP_D X        ; X := b (divisor)
POP_D Y        ; Y := a (dividend, becomes remainder)
SUB Q, Q       ; Q := 0 (quotient)
LOOP:
SUB Y, X
JS Y, RESTORE
ADD Q, 1
JMP LOOP
RESTORE:
ADD Y, X       ; undo the last over-subtraction
PUSH_D Y       ; remainder
PUSH_D Q       ; quotient
JMP NEXT
```

`/` and `MOD` each drop one of the two results `/MOD` leaves on the stack.

### `DO` / `LOOP` / `+LOOP`

No new opcodes: `DO` pushes `(limit, index)` with `PUSH_R`/`PUSH_R`; `LOOP` is `POP_R`/`POP_R`,
`ADD` the index, `SUB` against the limit, `JS`/`JZ` to decide whether to re-push and jump back to
the loop body or fall through. `+LOOP` is the same shape with the increment taken from the data
stack instead of hardcoded to 1. `I` is `R@` (already a `POP_R`/`PUSH_D`/`PUSH_R` idiom); nested
`J` reaches one loop-frame deeper on the return stack with two extra pop/push round-trips --
more microcode, still no new opcode.

### `EXECUTE` -- already free

`EXECUTE ( xt -- )` is `POP_D XT; JMP XT` -- exactly the tail of `NEXT` itself, once `XT` has
already been fetched. No new opcode, no new idiom.

## Coverage check against the design docs' word lists

| Category | Words | Built from |
| --- | --- | --- |
| Stack | `DUP DROP SWAP OVER ROT -ROT NIP TUCK` | Core only (`PUSH_D`/`POP_D`), as `minimal-itc-forth-primitives-{1,2,3}.md` already show |
| Arithmetic | `+ - * / MOD NEGATE ABS 1+ 1-` | `+`/`-`/`1+`/`1-`: core `ADD`/`SUB`. `*`: repeated-add loop. `/`, `MOD`: repeated-subtract loop. `NEGATE`, `ABS`: `SUB` self-zero idiom + `JS` |
| Memory | `@ ! C@ C!` | Core only. `C@`/`C!` are aliases of `@`/`!` in this design -- memory is cell-addressed with no separate byte granularity (matches `src/min_cpu_forth/cpu.py`'s flat `list[int]`) |
| Return stack | `>R R> R@` | Core only |
| Comparisons / logic | `= <> < > 0= 0< AND OR INVERT` | `=`/`<>`/`<`/`>`/`0=`/`0<`: `SUB` + `JZ`/`JS` boolean idiom. `AND`/`OR`/`INVERT`: new bitwise opcodes |
| Control / execution | `LIT DOCOL EXIT BRANCH 0BRANCH BYE/HALT` | Core only, exactly as `docs/design/instruction-set.md` already specifies |
| Loops | `DO LOOP +LOOP I` (`J` optional) | Core, using the `PUSH_R`/`POP_R`/`ADD`/`SUB`/`JS` idiom above |
| Outer interpreter | `EXECUTE` | Core only (free) |

Every word from the design conversation's own summary tables is accounted for by the 15-opcode
catalog. Nothing here requires a sixteenth opcode.

## Explicitly out of scope for this document

- **`WORD`, `FIND`, `NUMBER?`** (stage 7's outer-interpreter sketch): these need an addressable
  input text buffer and a dictionary search, both of which are algorithmically just more loops
  over `LOAD`/`SUB`/`JZ`/`JMP` comparing characters -- the opcode catalog above already covers
  what they'd need. Specifying the input buffer layout and dictionary search order is a separate
  design question, deferred to a later doc.
- **`U<`, `U>`** (unsigned comparison): `JS` tests the sign bit of a signed value; unsigned
  ordering needs a different test. Not part of the word list this document targets; flagged here
  so it isn't silently assumed to work.
- **Byte-level assembler encoding** (opcode numbers, operand encoding, instruction width): this
  document specifies opcode *semantics* only. Encoding them into the flat memory model is a
  separate concern -- see `docs/design/response-1.md`'s suggested opcode-list-as-bytes for a
  starting point, not yet reconciled with this catalog.
- **A real fetch/decode/execute loop.** As `docs/01-first-steps.md` found, no prototype and
  nothing currently in `src/min_cpu_forth/` executes an opcode stream -- everything runs at the
  Python-semantic level instead. This document is the ISA that loop would need to implement; it
  does not implement it.

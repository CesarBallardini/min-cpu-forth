awesome—let’s design a tiny, purpose-built virtual CPU (vCPU) that’s just enough to run an **Indirect-Threaded Code (ITC)** Forth the way your excerpt describes. I’ll give you a crisp spec: registers, memory map, word layout, and the minimal instruction set (including `NEXT`, `DOCOL`, `EXIT`, `LIT`, branches, and `DOES>` support). You can implement primitives in this vCPU and compile colon definitions as ITC threads of CFAs.

# vCPU Overview

* **Cell size:** 32 bits (one *cell* = 4 bytes).
* **Endianness:** little-endian.
* **Addressing:** byte-addressed; cell addresses advance by `+4`.
* **Stacks:** separate **Data Stack (D)** and **Return Stack (R)**, growing downwards.

# Registers

* **IP** (Interpreter Pointer): byte address into a thread (the Forth *program counter* for high-level words).
* **W**: holds the **Code Field Address (CFA)** of the word just entered (points at the *code field*).
* **XT**: scratch for the target native address loaded from the code field (destination of `NEXT`’s final jump).
* **DSP**: Data Stack Pointer (byte address; points to the top cell on the data stack).
* **RSP**: Return Stack Pointer (byte address; points to the top cell on the return stack).
* **PC**: the vCPU’s native program counter (executes vCPU opcodes for primitives).
* **T** *(optional but recommended)*: cached top-of-data-stack value to reduce memory traffic.

  * If implemented, keep `T` synchronized with `[DSP]` on pushes/pops.

> Minimality note: only **IP, W, DSP, RSP** are strictly necessary for ITC. **XT, PC, T** make the vCPU efficient and the microcode clean.

# Memory Map

```
0x0000_0000 ───────────────────────────────────────────────────────
            |  Reset/Trap vectors (optional)                      |
            |  Primitive code (vCPU instructions; read-only)      |
            |  System variables (e.g., BASE, HERE, LATEST)        |
            |                                                      |
            |  Dictionary space (grows up):                        |
            |    [Header][Code Field][Parameter Field ...]         |
            |         ^CF  ^CFA points here                        |
            |         PF begins at CFA + CELL                      |
            |                                                      |
            |  Free space                                          |
            |                                                      |
            |                           ┌───────────────────────┐  |
            |                           │ Return Stack (R)      │  |
     high → |                           │ ... grows downward ...│  |
            |                           └───────────────────────┘  |
            |                           ┌───────────────────────┐  |
            |                           │ Data Stack (D)        │  |
            |                           │ ... grows downward ...│  |
0xFFFF_FFFF ────────────────────────────┴───────────────────────┴──
```

You can choose exact stack bases; a typical setup:

* `D_BASE = 0xFF00_0000`, `DSP = D_BASE` (empty), grows to lower addresses.
* `R_BASE = 0xFF80_0000`, `RSP = R_BASE`, grows to lower addresses.
* `DICT_BASE = 0x0010_0000`, `HERE` grows upward.

# Forth Word Layout (ITC)

For a word `: SQUARE DUP * ;`:

```
[Header]
  link      (cell)  ← pointer to previous word's header
  flagsLen  (cell)  ← flags & name length (upper/lower bits as you like)
  name...   (bytes, padded to cell)

[Code Field]  CFA:
  cell = address of machine routine for this word
        - for colon defs: CFA = &DOCOL
        - for primitives: CFA = &that primitive's native entry

[Parameter Field]  PF (starts at CFA + CELL):
  For colon defs: a thread of CFAs (cells), typically ending with EXIT:
    cell: CFA(DUP)
    cell: CFA(*)
    cell: CFA(EXIT)
  For constants/variables: PF holds the data.
  For DOES>-defined words: PF is the body address passed to DOES> code.
```

# Execution Model (ITC “NEXT”)

Pseudocode for the inner interpreter step (`NEXT`), matching your excerpt:

```
NEXT:
  W  := [IP]               // fetch CFA address from thread
  IP := IP + CELL
  XT := [W]                // fetch native entry from code field
  JUMP XT                  // tail-call into the primitive at XT
```

Every primitive (including `DOCOL`, `EXIT`, etc.) ends by transferring control back to `NEXT` (tail call / jump), not `RET`.

# Minimal Instruction Set

The ISA is small and tuned to implement primitives cleanly. Mnemonics are one byte; immediates are 32-bit little-endian following the opcode. You can encode however you like; below is the semantic contract.

## Control / Threading

* `NEXT`
  Implements the ITC step above (uses IP, W, XT). Typically **not** emitted in threads; primitives end with `NEXT`.

* `DOCOL`

  ```
  [RSP] := IP;  RSP := RSP - CELL     // push IP to return stack
  IP := W + CELL                      // W points to code field; PF = CFA + CELL
  NEXT
  ```

* `EXIT`

  ```
  RSP := RSP + CELL;  IP := [RSP]     // pop IP from return stack
  NEXT
  ```

* `DODOES` *(for DOES> support)*
  Behavior when executing a DOES>-defined word whose CFA points to DODOES:

  ```
  [RSP] := IP;  RSP := RSP - CELL
  IP := [W + CELL]                    // PF holds address right after DOES> code
  PUSH (W + CELL)                     // push PFA (body) for DOES> part to use
  NEXT
  ```

  (Assembler/definer arranges that defining word rewrites CFAs of created words to CFA=DODOES and stores PFA appropriately.)

* `LIT`

  ```
  PUSH [IP]; IP := IP + CELL; NEXT
  ```

* `BRANCH +s32`

  ```
  IP := IP + offset; NEXT
  ```

* `0BRANCH +s32`

  ```
  POP x; if x == 0 then IP := IP + offset else IP := IP + 0; NEXT
  ```

> These are the only control primitives you need for colon code (`IF/ELSE/THEN`, `BEGIN/UNTIL`, `DO/LOOP` expand to these plus runtime loop params).

## Data Stack Primitives (can be opcodes or library primitives)

* `PUSH imm32`        → push immediate (handy for runtime code)
* `DROP`, `DUP`, `SWAP`, `OVER`, `ROT`, `-ROT`
* `>R`, `R>`, `R@`    → move between D and R stacks

*(You can also implement TOS-caching variants internally; the visible semantics are stack-based.)*

## ALU / Logic

* `+`, `-`, `*`, `UM*` (optional), `/MOD` or `/` and `MOD`
* `AND`, `OR`, `XOR`, `INVERT`
* `LSHIFT`, `RSHIFT`, `ARSHIFT` (optional)
* Comparisons returning true-as-all-ones (Forth style):
  `=`, `<>`, `<`, `>`, `U<`, `U>` , `0=`, `0<`

## Memory

* `@`     (fetch cell)        : `addr -- x`
* `!`     (store cell)        : `x addr --`
* `C@`, `C!` (byte fetch/store)
* `+!`    (add to cell)       : `x addr --`
* `CELL+` (addr arithmetic) can be a primitive or compiled macro.

*(All memory ops are little-endian, 32-bit cells.)*

## System / Misc

* `PCALL addr`  (call a vCPU subroutine, used by your runtime; returns with `RET`)
* `RET`         (return from `PCALL`)
* `TRAP code`   (I/O hook or error)
* `HALT`

> Most Forth *primitives* are best written as small vCPU subroutines that **end with `NEXT`** rather than `RET`. Reserve `PCALL/RET` for multi-step helper routines internal to a primitive.

# Required Primitives to Bootstrap ITC Forth

At minimum, implement these as native (vCPU) routines whose **entry addresses** are placed into CFAs:

* `DOCOL` (as above)
* `EXIT`
* `NEXT` (inner interpreter)
* `LIT`, `BRANCH`, `0BRANCH`
* `>R`, `R>`, `R@`
* `@`, `!`, `C@`, `C!`, `+!`
* `DUP`, `DROP`, `SWAP`, `OVER`
* `+`, `-`, `*`, `/MOD` (or `/`+`MOD`)
* `0=`, `<`, `U<`, `AND`, `OR`, `XOR`, `INVERT`
* `DODOES` (if you want `CREATE … DOES>`)

Everything else in standard Forth can be layered on top.

# Putting It Together: Example Layout

Assume:

* `CFA(DOCOL) = 0x0000_0200`
* `CFA(DUP)   = 0x0000_0300`
* `CFA(*)     = 0x0000_0320`
* `CFA(EXIT)  = 0x0000_0280`

And your dictionary allocates `SQUARE` at `HERE = 0x0010_1000`.

```
0x0010_1000: link     (cell)
0x0010_1004: flagsLen (cell)
0x0010_1008: 'S''Q''U''A''R''E' 0 0  (padded to cell boundary)

CFA:
0x0010_1010: 0x0000_0200           // &DOCOL

PF:
0x0010_1014: 0x0000_0300           // CFA(DUP)
0x0010_1018: 0x0000_0320           // CFA(*)
0x0010_101C: 0x0000_0280           // CFA(EXIT)
```

**Execution** when the thread reaches CFA(SQUARE):

1. `NEXT` loads `W := 0x0010_1010`, `IP += 4`, `XT := [W] = 0x0000_0200`, jumps to `DOCOL`.
2. `DOCOL` pushes old `IP`, sets `IP := W + 4 = 0x0010_1014`, then `NEXT`.
3. `NEXT` walks the PF: `DUP`, `*`, `EXIT`.

# Suggested Opcode List (concise)

You can adopt this literal list for a simple bytecode assembler:

```
00 NEXT
01 DOCOL
02 EXIT
03 DODOES
04 LIT <imm32>
05 BRANCH <rel32>
06 0BRANCH <rel32>

10 DROP
11 DUP
12 SWAP
13 OVER
14 ROT
15 -ROT

18 >R
19 R>
1A R@

20 +
21 -
22 *
23 /MOD
24 AND
25 OR
26 XOR
27 INVERT
28 0=
29 <
2A U<

30 @
31 !
32 C@
33 C!
34 +!

40 PCALL <abs32>
41 RET
7F HALT
```

(Feel free to tweak; the semantics above are the important bit.)

# Notes on DOES>

To support `CREATE name ... DOES> (runtime...)`:

* The **defining word** compiles code that, at `DOES>`, records the address of the runtime that follows and patches the created child’s **CFA** to `CFA(DODOES)`.
* When that child executes later, `DODOES`:

  * pushes `IP`,
  * sets `IP` to the recorded runtime address,
  * pushes the child’s **PFA** (`W + CELL`) so the runtime can use it,
  * then `NEXT`.

This matches classical ITC systems and keeps your interpreter small.

---

If you want, I can sketch the tiny microcode for `NEXT`, `DOCOL`, `EXIT`, `LIT`, and `0BRANCH` in your preferred assembler style (or target it to your Nga-like environment).

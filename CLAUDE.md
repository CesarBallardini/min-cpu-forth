# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A design exploration for a minimal virtual CPU instruction set purpose-built to run an
**Indirect Threaded Code (ITC) Forth** interpreter, now packaged as `src/min_cpu_forth`: a
`CPU` (flat memory, IP/W registers, data stack, return stack) and a `ForthExecutioner` (word
dictionary, colon definitions). Tooling — `uv`, `ruff`, `pyright`+`pyrefly`, `pytest`,
`bandit`/`pip-audit`/`OSV-Scanner`, `pre-commit` — was ported from the sibling
`../localenv-python` scaffold; see `README.md` for the full rundown and `make help` for every
available command.

## Running the code

Everything goes through the `Makefile` (wraps `uv`):

```
make install   # uv sync --all-groups --frozen; installs pre-commit hooks
make lint      # ruff check + ruff format --check
make format    # ruff format + ruff check --fix
make types     # pyright + pyrefly
make test      # pytest: unit + integration + acceptance (e2e excluded by default)
make security  # bandit + pip-audit + osv-scanner
```

`uv run --frozen python -c "from min_cpu_forth.forth import ForthExecutioner; ..."` reproduces
prototype demos interactively without a full script.

## Repository structure and how the pieces relate

- **`src/min_cpu_forth/`** — the maintained, tested implementation. `cpu.py` has `Stack` and
  `CPU`; `forth.py` has `ForthExecutioner`. This is where new Forth words, ISA changes, or VM
  fixes belong. Covered by `tests/unit/` and `tests/acceptance/` (pytest-bdd).

- **`docs/design/`** — the design conversation, read in this order to understand the current
  state of the design:
  1. `prompt-1.md` / `response-1.md` — the original design brief (a quoted article on ITC
     threading) and the first full response: registers, memory map, word layout, and a *broad*
     candidate instruction set (`NEXT`, `DOCOL`, `EXIT`, `DODOES`, `LIT`, `BRANCH`/`0BRANCH`,
     plus many stack/ALU/memory opcodes).
  2. `instruction-set.md` — the design narrows to the actual minimal instruction set: just
     `LOAD`, `STORE`, `ADD`, `JMP`, `JZ`, `PUSH_D`/`POP_D`, `PUSH_R`/`POP_R`, `HALT`. Everything
     else (`DUP`, `+`, `@`, ...) must be built as microcode on top of these ops. This file is
     the canonical ISA reference — later docs build on it, not on `response-1.md`'s larger
     opcode list.
  3. `minimal-itc-forth-primitives-{1..6}.md` — successive passes at writing the microcode for
     Forth primitives strictly in terms of the ISA from `instruction-set.md`. Files 1 and 2
     cover the same ground twice (near-duplicates); later files extend into `IF/ELSE/THEN`,
     `BEGIN/UNTIL`, `DO/LOOP` compilation, and (in file 6) a self-hosted `NEXT`
     outer-interpreter loop written in Forth itself. Treat the **highest-numbered file**
     covering a given word as the most current version.

- **`docs/prototypes/`** — the four original `assembler-interpreter-{1..4}.py` scripts, kept
  verbatim as historical reference and **frozen** (superseded by `src/min_cpu_forth/`, not
  extended further):
  - `-1.py`: full `CPU`/`Stack`/`Instruction` class hierarchy plus a `ForthVM` with a real
    dictionary, `NEXT`-style inner interpreter, and colon-definition compilation. Closest to
    the ISA described in `docs/design/`.
  - `-2.py`: a simplified, more Pythonic `CPU`/`ForthExecutioner` where Forth words are plain
    Python closures over a `dict`, not compiled threads — no real ITC execution model, just a
    stack-machine simulation for quick testing of word semantics.
  - `-3.py`: an *incremental patch* layered on top of `-2.py`'s classes — meant to be read
    together with `-2.py`, not standalone.
  - `-4.py`: `-2.py` and `-3.py` merged into one consistent file. This is what
    `src/min_cpu_forth/` was consolidated from.

- **`minimal-cpu-forth.tgz`** (repo root) — a tarball snapshot predating this reorganization.
  It is a backup/archive, not a separate source of truth; do not edit files inside it, and
  don't treat divergence between the tarball and the working tree as a real change unless asked.

## Design invariants to preserve when extending this work

- The canonical minimal ISA is exactly the 8 ops in `instruction-set.md`
  (`LOAD`, `STORE`, `ADD`, `JMP`, `JZ`, `PUSH_D`, `POP_D`, `PUSH_R`, `POP_R`, `HALT`). Any new
  primitive's microcode should be expressible in terms of these — if it isn't, that's worth
  flagging rather than silently adding a new opcode.
- ITC execution model: a word's Code Field Address (CFA) holds the address of native code to run;
  colon definitions have CFA = address of `DOCOL`, and their Parameter Field is a thread of CFAs
  terminated by `EXIT`'s CFA. `NEXT` does the double-indirection `IP -> W -> XT` and tail-jumps
  (never `CALL`/`RET`) into the primitive.
- Every primitive routine ends by jumping to `NEXT`, not by returning — this is what makes it
  threaded code rather than ordinary subroutine calls.
- The data stack and return stack must occupy non-overlapping memory regions. The `-4.py`
  prototype started both stacks at the same base address (never caught because its demos never
  exercised the return stack); `src/min_cpu_forth/cpu.py` fixes this by giving each stack its
  own region (`DATA_STACK_BASE`/`RETURN_STACK_BASE`). Preserve that separation in any further
  changes to memory layout.

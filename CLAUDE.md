# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A design exploration for a minimal virtual CPU instruction set purpose-built to run an
**Indirect Threaded Code (ITC) Forth** interpreter, packaged as `src/min_cpu_forth` and built as
a **hexagonal (ports-and-adapters) architecture** wired by `dependency-injector`. The `domain`
layer holds the ISA enums and the boundary DTOs; `services` (`EmulatorService`, `ForthService`,
and the Phase 0 assembler pipeline) depend only on the port Protocols in `ports.py`; `adapters`
supply the concrete memory/stack/register/character-I/O implementations; and `containers.py` is
the composition root that alone binds adapters to ports. The hexagon's dependency rule is
machine-enforced by `import-linter` (`.importlinter`). Tooling — `uv`, `ruff`,
`pyright`+`pyrefly`, `pytest`, `bandit`/`pip-audit`/`OSV-Scanner`, `import-linter`, `pre-commit`
— was ported from the sibling `../localenv-python` scaffold (`dependency-injector` and
`import-linter` were added for this architecture); see `README.md` for the full rundown and
`make help` for every available command.

## Running the code

Everything goes through the `Makefile` (wraps `uv`):

```
make install       # uv sync --all-groups --frozen; installs pre-commit hooks
make lint          # ruff check + ruff format --check + import-linter contracts
make architecture  # import-linter only (the hexagonal dependency rules)
make format        # ruff format + ruff check --fix
make types         # pyright + pyrefly
make test          # pytest: unit + integration + acceptance (e2e excluded by default)
make security      # bandit + pip-audit + osv-scanner
```

Build a machine through the composition root rather than instantiating classes directly:
`uv run --frozen python -c "from min_cpu_forth.containers import MachineContainer; f = MachineContainer().forth(); ..."`
reproduces prototype demos interactively without a full script.

## Repository structure and how the pieces relate

- **`src/min_cpu_forth/`** — the maintained, tested implementation, organized as a hexagon whose
  dependency arrows point inward (enforced by `.importlinter`). New Forth words, ISA changes, VM
  fixes, or assembler work belong here; pick the layer by responsibility. Covered by
  `tests/unit/` and `tests/acceptance/` (pytest-bdd).
  - **`domain/`** — pure value objects, no dependency on any other layer: `opcode.py`
    (`Opcode` (a `StrEnum`)/`InstructionField`/`OperandKind`), `types.py` (the `Address`/
    `ProgramIndex`/`Cell` `NewType`s that make the Harvard split nominal), `register.py`
    (`Register`, a `StrEnum` for the reserved machine registers), and `dtos.py` (the `*Dto`
    boundary types `InstructionDto`/`AssemblyDto`/`KernelImageDto`/`WordSpecDto`/`ThreadItemDto`/
    `DictionaryHeaderDto` …, plus the static `OperandSpec` and `HeaderField`, the header layout).
  - **`ports.py`** — the boundary Protocols (`MemoryPort`, `StackPort`, `RegisterFilePort`,
    `CharacterInput/OutputPort`, `DictionaryPort` and `SystemVariablesPort`, and the
    assembler-pipeline ports). Services are typed against these, never against a concrete adapter.
  - **`services/`** — the use cases, depending only on ports: `emulator.py`'s `EmulatorService`
    (a real fetch-decode-execute loop over `InstructionDto`s -- `docs/02-cpu-design.md`'s
    17-opcode ISA, closing `docs/01-first-steps.md`'s "no prototype ever emulated the opcode
    level" gap), `forth.py`'s `ForthService` (Forth *semantics* -- stack effects, `DOCOL`/`EXIT`,
    colon definitions -- the direct Python model), `assembler/` (the Phase 0 parse → resolve →
    emit pipeline of `docs/03-assembler-plan.md`), and `kernel/` (Phases 1-2: `routines.py`'s ITC
    threading core plus the `PRIMITIVES` word table as assembler source, and `builder.py`'s
    `KernelBuilder`, which installs words through a `DictionaryPort` so a colon definition runs
    through genuine `NEXT`/`DOCOL`/`EXIT`; `builder.py` also holds the `boot`/`boot_thread` helpers).
  - **`adapters/`** — concrete port implementations (`ListMemoryAdapter`, `DownwardStackAdapter`,
    `DictRegisterFileAdapter`, `QueueCharacterInputAdapter`, `BufferCharacterOutputAdapter`,
    `StringSourceAdapter`, `MemoryDictionaryAdapter` (owns the header layout + link chain), and
    `MemorySystemVariablesAdapter` (`DP`/`LATEST`)), independent of `services/`.
  - **`containers.py`** — `MachineContainer`/`AssemblerContainer`, the `dependency-injector`
    composition root and the only place adapters meet ports. **`errors.py`** (the `MachineError`
    hierarchy) and **`layout.py`** (the `cpu.mem` memory-map constants) are the shared kernel.
  - `docs/03-assembler-plan.md` is the phased plan for running Forth on `EmulatorService`;
    **Phases 0-2 and 4 (the assembler, the ITC threading core, the core primitive word set, and the
    I/O + dictionary-search words) are built**; Phase 3 (branching/loop runtime) is skipped for now,
    and Phases 5+ are not yet.

- **`docs/01-first-steps.md`**, **`docs/02-cpu-design.md`**, and **`docs/03-assembler-plan.md`**
  — read these, in order, before the raw design conversation below. `01` is a reviewer's
  walk-through of how the design and the four prototypes evolved (and where they disagree with
  each other); `02` is the reconciled, justified 17-opcode ISA that `emulator.py` implements;
  `03` is the phased plan -- informed by Brad Rodriguez's "Moving Forth" series and CamelForth --
  for the ITC Forth kernel that hasn't been built yet.

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

- The canonical minimal ISA is exactly the 10 ops in `instruction-set.md`
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
  exercised the return stack); `layout.py` fixes this by giving each stack its own region
  (`DATA_STACK_BASE`/`RETURN_STACK_BASE`), and `MachineContainer` wires a `DownwardStackAdapter`
  over each. Preserve that separation in any further changes to memory layout.
- Architecture invariants (checked by `make lint` via `import-linter`): the dependency rule
  points inward (`containers` → `services`|`adapters` → `ports` → `domain`), services depend on
  ports and never on concrete adapters, and `domain` imports nothing from the outer layers — both
  contracts live in `.importlinter`. Keep the code fully typed (no `Any`/`object`; `pyright`
  **and** `pyrefly` must pass), suffix boundary data structures with `Dto`, and when you add a new
  port, register a concrete adapter for it in a `Container` rather than instantiating it directly.

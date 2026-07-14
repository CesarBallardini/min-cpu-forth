# min-cpu-forth

[![check](https://github.com/CesarBallardini/min-cpu-forth/actions/workflows/check.yml/badge.svg)](https://github.com/CesarBallardini/min-cpu-forth/actions/workflows/check.yml)
[![pytest](https://github.com/CesarBallardini/min-cpu-forth/actions/workflows/pytest.yml/badge.svg)](https://github.com/CesarBallardini/min-cpu-forth/actions/workflows/pytest.yml)
[![security](https://github.com/CesarBallardini/min-cpu-forth/actions/workflows/security.yml/badge.svg)](https://github.com/CesarBallardini/min-cpu-forth/actions/workflows/security.yml)

A design exploration of a minimal virtual CPU instruction set purpose-built to run an
**Indirect Threaded Code (ITC) Forth** interpreter, plus a Python implementation of that
model: a small `CPU` (flat memory, a data stack, and a return stack) and a `ForthExecutioner`
that installs the Forth word dictionary and supports colon definitions.

`docs/design/` has the full design conversation (registers, memory map, word layout, and the
minimal instruction set the CPU is meant to expose); `docs/prototypes/` has the four earlier,
throwaway Python scripts this package was consolidated from -- kept as historical reference,
not maintained further. Read [`docs/01-first-steps.md`](docs/01-first-steps.md) first: it walks
through that history in order and calls out where the design and the code disagree.
[`docs/02-cpu-design.md`](docs/02-cpu-design.md) picks up from there with a reconciled,
justified opcode catalog for a CPU that can actually run the minimal Forth word list. See
`CLAUDE.md` for how the pieces fit together.

The design in `docs/design/` originated from a conversation with ChatGPT-4, seeded with an
excerpt from Brad Rodriguez's article
["Moving Forth: Part 1 -- The Threading Technique"](https://www.bradrodriguez.com/papers/moving1.htm)
(`docs/design/prompt-1.md`), which explains classical Indirect Threaded Code (ITC).

# What's in here

* **[uv](https://docs.astral.sh/uv/)** for dependency and environment management.
* **[ruff](https://docs.astral.sh/ruff/)** as linter and formatter (`ruff.toml`).
* **[pyright](https://microsoft.github.io/pyright/)** + **[pyrefly](https://pyrefly.org/)** as a pair of type checkers, run on purpose, not mid-migration (`pyrightconfig.json`, `pyrefly.toml`).
* **[bandit](https://bandit.readthedocs.io/)** (SAST) with a baseline, and **[pip-audit](https://pypi.org/project/pip-audit/)** + **[OSV-Scanner](https://google.github.io/osv-scanner/)** (SCA) against `uv.lock` for security (`bandit.yaml`). OSV-Scanner is a standalone Go binary, not a PyPI package, so it doesn't go through `uv` -- locally it just needs to be on `PATH` (`choco install osv-scanner` on Windows), in CI it runs via Google's official reusable workflow (see `security.yml`).
* **[pytest](https://docs.pytest.org/)** with tests split by kind: `unit/`, `integration/` (placeholder), `acceptance/` (BDD via [pytest-bdd](https://pytest-bdd.readthedocs.io/)), `e2e/` (placeholder, via [pytest-playwright](https://playwright.dev/python/docs/test-runners)).
* **[pre-commit](https://pre-commit.com/)** hooking lint, format, and lockfile checks before every commit.
* A `Makefile` as the single interface -- nobody needs to memorize the exact command for each tool.
* Three independent GitHub Actions workflows in `.github/workflows/`, one per concern: `check.yml` (lint + format + types), `pytest.yml`, `security.yml` (bandit + pip-audit + OSV-Scanner).

# Prerequisites

* [uv](https://docs.astral.sh/uv/) (verified with the latest stable release)
* Python 3.14 (uv installs it automatically if missing, per `.python-version`)
* Git
* [OSV-Scanner](https://google.github.io/osv-scanner/) on `PATH` (only needed for `make security`; on Windows, `choco install osv-scanner`)

# Using this repository

Install dependencies and the pre-commit hooks:

```bash
make install
```

From there, everything goes through the Makefile:

```bash
make                  # no target: lists all available targets
make lint             # ruff check + ruff format --check
make format           # ruff format + ruff check --fix
make types            # pyright + pyrefly
make test             # pytest (unit + integration + acceptance; e2e excluded by default)
make test-bdd         # only the acceptance tests (pytest -m bdd)
make test-integration # only the integration tests (pytest -m integration)
make test-e2e         # pytest -m e2e (requires Playwright installed: uv run --frozen playwright install)
make security         # bandit + pip-audit --skip-editable + osv-scanner
make precommit        # run all pre-commit hooks by hand
```

# Structure

```
src/min_cpu_forth/
  cpu.py                  # Stack, CPU: flat memory, IP/W registers, data + return stacks
  forth.py                # ForthExecutioner: word dictionary, colon definitions
docs/
  design/                 # the design conversation: registers, memory map, instruction set
  prototypes/             # the four original assembler-interpreter-*.py scripts (frozen)
tests/
  unit/                    # no infrastructure, fast (test_cpu.py, test_forth.py)
  integration/             # need a real service (placeholder, not used yet)
  acceptance/
    features/               # .feature files (Gherkin) -- square.feature
    steps/                   # pytest-bdd step definitions
  e2e/                      # against a running instance (placeholder, not used yet)
```

# Updating dependencies

By default, `uv run` and `uv sync` can re-resolve and rewrite `uv.lock` on their own if they
detect `pyproject.toml` changed. That's fine for day-to-day use, but for any command that's
meant to just *run* something (CI, onboarding, any given `make test`), it's worth pinning the
lockfile to exactly what's committed, so a routine run doesn't end up touching `uv.lock`
without anyone asking for it:

```bash
uv sync --frozen              # installs exactly what uv.lock says, resolves nothing
uv run --frozen pytest        # same idea, for any one-off command
```

The local pre-commit hook (`uv lock --check`) already fails if `uv.lock` drifts out of sync
with `pyproject.toml` -- so a `uv sync`/`uv run` without `--frozen` that accidentally rewrites
the lock gets caught before the commit, not in CI.

To update dependencies **on purpose**, the flow is explicit, never implicit:

```bash
uv lock --upgrade-package ruff   # updates just that package to the max pyproject.toml allows
uv lock --upgrade                # updates everything pyproject.toml's constraints allow
```

Both commands rewrite `uv.lock` -- review the diff (`git diff uv.lock`) before continuing.
After updating, run the full suite before committing:

```bash
uv sync --all-groups   # installs whatever just landed in the updated lock
make lint types test security
```

# License

MIT — see [LICENSE](LICENSE).

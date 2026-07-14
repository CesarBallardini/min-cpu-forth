.DEFAULT_GOAL := help

.PHONY: help install lint architecture format types test test-bdd test-integration test-e2e security precommit

help: ## Show this list of available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Sync the environment (from the committed lockfile) and install pre-commit hooks
	uv sync --all-groups --frozen
	uv run --frozen pre-commit install

lint: ## Check formatting, lint rules, and architecture without modifying files
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .
	uv run --frozen lint-imports

architecture: ## Check the hexagonal import contracts (import-linter)
	uv run --frozen lint-imports

format: ## Auto-fix formatting and lint issues
	uv run --frozen ruff format .
	uv run --frozen ruff check --fix .

types: ## Run both type checkers (pyright + pyrefly)
	uv run --frozen pyright
	uv run --frozen pyrefly check

test: ## Run the test suite (unit + integration + acceptance; e2e excluded by default)
	uv run --frozen pytest

test-bdd: ## Run only the BDD/acceptance tests (pytest-bdd)
	uv run --frozen pytest -m bdd

test-integration: ## Run only the integration tests (need a real DB/service)
	uv run --frozen pytest -m integration

test-e2e: ## Run end-to-end tests (requires: uv run --frozen playwright install)
	uv run --frozen pytest -m e2e

security: ## Run security scans (bandit SAST + pip-audit + OSV-Scanner SCA)
	uv run --frozen bandit -c bandit.yaml -r src
	uv run --frozen pip-audit --skip-editable
	osv-scanner --lockfile=./uv.lock

precommit: ## Run all pre-commit hooks against every file
	uv run --frozen pre-commit run --all-files

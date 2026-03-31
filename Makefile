# SurveyMind Makefile

.PHONY: help install test lint format clean run-survey validate check-arxiv install-dev

help:
	@echo "SurveyMind development commands:"
	@echo "  make install       Install dependencies (requires internet)"
	@echo "  make install-dev   Install dev dependencies (pytest, ruff, …)"
	@echo "  make test          Run the test suite"
	@echo "  make lint          Run ruff linting"
	@echo "  make format        Auto-format code with ruff"
	@echo "  make check-arxiv  Quick smoke-test: search arXiv API"
	@echo "  make clean         Remove generated files"

# ── Environment ──────────────────────────────────────────────────────────────────

VENV := .venv
PYTHON := $(VENV)/bin/python

# ── Dependencies ────────────────────────────────────────────────────────────────

install:
	@echo "Installing SurveyMind dependencies…"
	pip install --upgrade pip
	pip install -e .
	pip install httpx requests

install-dev: install
	@echo "Installing dev dependencies…"
	pip install pytest pytest-mock responses ruff

# ── Tests ───────────────────────────────────────────────────────────────────────

test:
	@echo "Running test suite…"
	pytest tests/ -v

# ── Lint & format ───────────────────────────────────────────────────────────────

lint:
	@echo "Running ruff lint…"
	ruff check tools/ mcp-servers/ validation/ --output-format=concise

format:
	@echo "Formatting code with ruff…"
	ruff format tools/ mcp-servers/ validation/
	ruff check tools/ mcp-servers/ validation/ --fix

check-arxiv:
	@echo "Testing arXiv API access…"
	python3 -c "from tools.arxiv_client import search; r=search('id:2301.07041', max_results=1); print(f'OK: found {len(r)} paper')"

# ── Validation ──────────────────────────────────────────────────────────────────

validate:
	python3 validation/run_validation.py --scope all

# ── Clean ──────────────────────────────────────────────────────────────────────

clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -delete
	find . -name ".pytest_cache" -type d -delete
	find . -name "*.log" -delete
	rm -rf surveys/survey_*/paper_analysis_results/*.md
	rm -rf tmp/

# ── Run ─────────────────────────────────────────────────────────────────────────

run-survey:
	python3 tools/surveymind_run.py --stage all

# ── Development helpers ─────────────────────────────────────────────────────────

check-deps:
	@python3 -c "import httpx, requests" 2>/dev/null && echo "httpx, requests: OK" || echo "httpx or requests: MISSING"
	@python3 -c "import pytest" 2>/dev/null && echo "pytest: OK" || echo "pytest: MISSING"
	@python3 -c "import ruff" 2>/dev/null && echo "ruff: OK" || echo "ruff: MISSING"

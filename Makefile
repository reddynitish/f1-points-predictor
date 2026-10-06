.PHONY: install format lint typecheck test check collect-offline clean

install:
	uv sync --locked

format:
	uv run ruff format src tests scripts
	uv run ruff check --fix src tests scripts

lint:
	uv run ruff format --check src tests scripts
	uv run ruff check src tests scripts

typecheck:
	uv run mypy

test:
	uv run pytest -q

# What CI runs. Fails on formatting drift instead of rewriting files.
check: lint typecheck test

# Replays the cached snapshots; never downloads. Needs a prior online collect.
collect-offline:
	uv run python -m f1_points.cli collect --offline --report data/offline-coverage.json

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

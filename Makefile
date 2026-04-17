.PHONY: install test lint format clean init build

install:
	pip install -e ".[dev]"

test:
	pytest src/tests/ -v --cov=src --cov-report=term-missing

test-unit:
	pytest src/tests/unit/ -v

test-graph:
	pytest src/tests/graph/ -v

test-eval:
	pytest src/tests/evaluation/ -v

lint:
	ruff check src/
	mypy src/

format:
	black src/
	ruff check --fix src/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov
	rm -f knowledge_system.db knowledge_graph.json

init:
	python -m src.cli init

build: format lint test

run-workflow:
	python -m src.cli full-workflow --owner example --repo example-repo

.PHONY: install test lint format clean build publish

# Install in development mode
install:
	pip install -e .[dev]

# Run tests
test:
	python scripts/smoke_test.py
	pytest tests/ -v --tb=short

# Lint
lint:
	ruff check .

# Format
format:
	ruff check --fix .
	# black .

# Type check
typecheck:
	mypy sculpt/

# Clean
clean:
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

# Build package
build: clean
	pip install build
	python -m build

# Publish to PyPI
publish: build
	twine upload dist/*

# Install pre-commit hooks
pre-commit:
	pre-commit install

# Quick test
quicktest:
	python scripts/smoke_test.py

# Install for development
dev-install:
	pip install -e .[dev]
	pre-commit install

# Run a quick generation test (requires network)
demo:
	python -m sculpt generate --prompt "a simple cube"
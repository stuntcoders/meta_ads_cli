.PHONY: install test lint run

install:
	python3 -m pip install -e .[dev]

test:
	python3 -m pytest

lint:
	python3 -m ruff check src tests

run:
	python3 -m meta_cli.app --help

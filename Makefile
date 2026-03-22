.PHONY: install install-lock lock test lint run

install:
	python3 -m pip install -e .[dev]

install-lock:
	python3 -m pip install -r requirements-dev.lock

lock:
	python3 -m piptools compile --output-file requirements.lock requirements.in
	python3 -m piptools compile --output-file requirements-dev.lock requirements-dev.in

test:
	python3 -m pytest

lint:
	python3 -m ruff check src tests

run:
	python3 -m meta_cli.app --help

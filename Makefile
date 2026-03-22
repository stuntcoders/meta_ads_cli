.PHONY: install install-lock install-global-local lock build test lint run

install:
	python3 -m pip install -e .[dev]

install-lock:
	python3 -m pip install -r requirements-dev.lock

install-global-local:
	python3 -m pip install --user pipx
	python3 -m pipx ensurepath
	python3 -m pipx install --force .

lock:
	python3 -m piptools compile --output-file requirements.lock requirements.in
	python3 -m piptools compile --output-file requirements-dev.lock requirements-dev.in

build:
	python3 -m pip install --user build
	python3 -m build

test:
	python3 -m pytest

lint:
	python3 -m ruff check src tests

run:
	PYTHONPATH=src python3 -m meta_cli --help

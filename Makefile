.PHONY: install install-lock install-pipx-local install-pipx-git install-global-local lock build brew-formula test lint run

install:
	python3 -m pip install -e .[dev]

install-lock:
	python3 -m pip install -r requirements-dev.lock

install-pipx-local:
	python3 -m pip install --user pipx
	python3 -m pipx ensurepath
	python3 -m pipx install --force .

install-pipx-git:
	python3 -m pip install --user pipx
	python3 -m pipx ensurepath
	python3 -m pipx install --force "git+https://github.com/stuntcoders/meta_ads_cli.git"

# Backward-compatible alias
install-global-local: install-pipx-local

lock:
	python3 -m piptools compile --strip-extras --output-file requirements.lock requirements.in
	python3 -m piptools compile --strip-extras --output-file requirements-dev.lock requirements-dev.in

build:
	python3 -m pip install --user build
	python3 -m build

brew-formula:
	@test -n "$(HOMEPAGE)" || (echo "HOMEPAGE is required" && exit 1)
	@test -n "$(SOURCE_URL)" || (echo "SOURCE_URL is required" && exit 1)
	@test -n "$(SOURCE_SHA256)" || (echo "SOURCE_SHA256 is required" && exit 1)
	python3 scripts/generate_brew_formula.py \
		--homepage "$(HOMEPAGE)" \
		--source-url "$(SOURCE_URL)" \
		--source-sha256 "$(SOURCE_SHA256)" \
		--output "$(or $(OUTPUT),Formula/meta-ads-cli.rb)"

test:
	python3 -m pytest

lint:
	python3 -m ruff check src tests

run:
	PYTHONPATH=src python3 -m meta_cli --help

#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/release_brew_formula.sh \
#     --homepage "https://github.com/<org>/<repo>" \
#     --source-url "https://github.com/<org>/<repo>/archive/refs/tags/v0.1.0.tar.gz" \
#     --source-sha256 "<sha256>" \
#     --output "./Formula/meta-ads-cli.rb"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/generate_brew_formula.py "$@"

echo "Formula generated. Commit it to your tap repo under Formula/meta-ads-cli.rb"

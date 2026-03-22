# AGENTS.md

Repository operating instructions for coding agents (including future/resurrected sessions).

## Mission

Maintain and extend `meta-cli` as a production-grade Meta Ads CLI with strong safety, tests, and operator UX.

## Non-negotiables

1. **Keep README fully up to date with every behavior change.**
   - If commands, flags, workflows, or outputs change, update README in the same milestone.
2. **Run relevant validation before every commit.**
   - Minimum standard for most code changes:
     - `python3 -m ruff check src tests`
     - `python3 -m pytest`
3. **Commit discipline**
   - Make small, logical commits.
   - Use concise commit messages.
   - Do not batch unrelated changes.
4. **Safety-first defaults**
   - Preserve PAUSED defaults for spend-affecting create flows unless explicitly requested.
   - Keep confirmations for pause/resume or spend-affecting operations unless `--yes` is passed.

## Development workflow (agent loop)

For each milestone:

1. Inspect current repository state and related files.
2. Plan minimal concrete change.
3. Implement.
4. Run lint/tests relevant to changed surface.
5. Fix failures.
6. Update README/docs/examples if behavior changed.
7. Commit.

## Project conventions

- Python 3.12+ target
- Typer CLI
- Meta official `facebook-business` SDK only
- Pydantic validation for configs/schemas
- PyYAML for config files
- Pytest with mocks for non-live tests
- Keep architecture thin/readable (`sdk.py` + command modules)

## Testing guidance

- Prefer mocked unit tests for CLI/service behavior.
- Live tests stay opt-in under `tests/integration` with `LIVE_META_TESTS=1`.
- For workflow/script changes, add/update tests where practical.

## Packaging and distribution

- Keep these paths healthy when changed:
  - `pyproject.toml`
  - `requirements*.in` and `requirements*.lock`
  - `.github/workflows/release-and-publish.yml`
  - `.github/workflows/homebrew-formula-pr.yml`
  - `scripts/generate_brew_formula.py`
- If release/homebrew behavior changes, update README sections for release + tap automation.

## Release/homebrew automation notes

- Release workflow (`release-and-publish.yml`) is the one-click entry point.
- Homebrew workflow (`homebrew-formula-pr.yml`) opens PRs against tap repo.
- Required GitHub settings are documented in README; keep that section current.

## Guardrails

- Do not require secrets to run tests.
- Do not remove existing safety checks without explicit request.
- Do not perform destructive external actions unless clearly requested.

## Definition of done for changes

- Code works
- Tests pass
- Lint passes
- README updated (if behavior changed)
- Commit created

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
5. **Promote script-only operations into CLI features**
   - If an agent uses an ad-hoc Python script to perform a useful/recurring operation (especially with the Meta SDK), treat that as product debt.
   - Add or extend a first-class `meta-cli` command/flag for that operation in the same milestone when practical.
   - Add/update tests and README examples for the new CLI surface so users do not need ad-hoc scripts for that workflow.

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

## Named environment operations (required)

`meta-cli` uses persistent named environments so operators do not accidentally act on the wrong Meta account.

- The expected operator profile slugs are:
  - `hoca-rehberi`
  - `mentor-maam`
  - `privatni-casovi`
- Profiles are stored outside the repository in `$META_CLI_ENVIRONMENTS_FILE`, `$XDG_CONFIG_HOME/meta-ads-cli/environments.yaml`, or `~/.config/meta-ads-cli/environments.yaml` (in that precedence order).
- Never add the real environment store, access tokens, or app secrets to Git, fixtures, documentation, command output, logs, or commits. Never print/cat the raw store. Keep it owner-only (`0600`).
- Do not assume which profile is active. Selection persists across invocations. Before any live Meta operation, run `meta-cli environments current` and verify the target account. Use `meta-cli environments use <name>` only when the user explicitly asks to switch environments.
- Do not silently switch to another profile for validation and switch back afterward. Use a safe explicit auth override where appropriate, or ask the user to authorize the switch.
- Standard commands must continue to require a selected named environment. Do not restore ambient `META_*` credentials as an implicit fallback. Explicit legacy `--config`/`--auth-config` files remain deliberate overrides.
- A complete profile requires `access_token`, `app_id`, `app_secret`, `ad_account_id`, and `api_version`. Preserve optional `system_user_id`, `facebook_page_id`, and `instagram_user_id`; Page and Instagram IDs provide ad-creative identity defaults.
- Preserve atomic environment-store writes, secret redaction, profile validation, and `0600` permissions. Never overwrite the store in a way that drops unrelated profiles or changes `active_profile` unintentionally.
- The current recommended Meta Marketing API/SDK line is `v25.0` / `facebook-business>=25.0.2`. Verify official Meta support before changing it, and update dependencies, lock files, tests, README, and setup docs together.
- Environment management belongs in first-class CLI commands (`meta-cli environments ...`), not recurring ad-hoc scripts.

## Testing guidance

- Prefer mocked unit tests for CLI/service behavior.
- Live tests stay opt-in under `tests/integration` with `LIVE_META_TESTS=1`.
- Tests must set `META_CLI_ENVIRONMENTS_FILE` to a temporary path so they never read, select, rewrite, or leak the operator's real profiles.
- Never use real credentials in unit tests. Live credential tests must remain explicit, read-only, and isolated from the persistent active-profile selection where practical.
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
- Treat campaign/ad set/ad creation, activation, budget changes, targeting replacement, and creative replacement as live account mutations. Confirm the active environment and preserve confirmation/`--dry-run` protections before executing them.
- Authentication checks, environment inspection, and read-only listings/reports may be used for validation, but must not change the persistent environment unless explicitly requested.

## Definition of done for changes

- Code works
- Tests pass
- Lint passes
- README updated (if behavior changed)
- Commit created

# Meta Ads CLI (`meta-cli`)

Production-grade Python CLI for managing Meta ads with the **official Meta Python Business SDK**.

## What this CLI does

- Validate Meta auth and account access
- List campaigns, ad sets, ads, and inspect ad creatives
- Fetch ad insights/performance metrics
- Save read-only account snapshots with recurring period insights
- Upload image/video assets
- Create campaigns, ad sets, and ads from YAML or flags
- Pause/resume campaigns, ad sets, ads
- Search Meta targeting locations and replace ad set targeting from JSON or YAML
- Update an ad to use a different creative

---

## Prerequisites

- Python 3.12+
- A Meta app with Marketing API access
- Meta ad account access with required permissions
- Valid Meta access token

---

## Meta setup and configuration

Full setup/configuration guide:

- [`docs/meta-setup-and-configuration.md`](docs/meta-setup-and-configuration.md)

---

## Installation

### Recommended install paths

- **macOS:** Homebrew
- **Ubuntu/Debian/other Linux distros:** pipx

### 1) Homebrew install (macOS, recommended)

Tap repository URL:

- `https://github.com/stuntcoders/homebrew-meta-ads-cli`

Install:

```bash
brew tap stuntcoders/meta-ads-cli
brew install stuntcoders/meta-ads-cli/meta-ads-cli
```

Verify:

```bash
meta-cli --help
```

Upgrade:

```bash
brew update
brew upgrade meta-ads-cli
```

### 2) pipx install (for Ubuntu, Debian, and other Linux distros)

If `pipx` is not installed:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Install latest from repository:

```bash
pipx install "git+https://github.com/stuntcoders/meta_ads_cli.git"
```

Install a pinned release tag:

```bash
pipx install "git+https://github.com/stuntcoders/meta_ads_cli.git@v0.1.0"
```

Verify:

```bash
meta-cli --help
```

Upgrade later:

```bash
pipx upgrade meta-ads-cli
```

### 3) Local source install (less common; maintainers/advanced users)

Repository URL:

- `https://github.com/stuntcoders/meta_ads_cli`

Install from source:

```bash
git clone https://github.com/stuntcoders/meta_ads_cli.git
cd meta_ads_cli
python3 -m pip install .
```

Dev editable install:

```bash
python3 -m pip install -e ".[dev]"
```

---

## Configuration

### Set up a named environment

The recommended workflow stores all named profiles in one private YAML file. The path is:

- `$META_CLI_ENVIRONMENTS_FILE` when set (recommended for tests and automation)
- `$XDG_CONFIG_HOME/meta-ads-cli/environments.yaml` when `XDG_CONFIG_HOME` is set
- `~/.config/meta-ads-cli/environments.yaml` otherwise

The default expands to an absolute path such as:

- macOS: `/Users/<your-username>/.config/meta-ads-cli/environments.yaml`
- Linux: `/home/<your-username>/.config/meta-ads-cli/environments.yaml`

Create the parent directory and a multi-environment file, then protect it because it contains access
tokens and app secrets:

```bash
mkdir -p "$HOME/.config/meta-ads-cli"
cat > "$HOME/.config/meta-ads-cli/environments.yaml" <<'YAML'
# Keep null during initial setup. Select with `meta-cli environments use <name>`.
active_profile: null
profiles:
  brand-a:
    display_name: Brand A
    access_token: "replace-with-brand-a-system-user-token"
    app_id: "replace-with-brand-a-app-id"
    app_secret: "replace-with-brand-a-app-secret"
    ad_account_id: "act_111111111111111"
    api_version: "v25.0"
    # Optional metadata and ads-create identity defaults:
    system_user_id: "replace-with-brand-a-system-user-id"
    facebook_page_id: "replace-with-brand-a-page-id"
    instagram_user_id: "replace-with-brand-a-instagram-user-id"

  brand-b:
    display_name: Brand B
    access_token: "replace-with-brand-b-system-user-token"
    app_id: "replace-with-brand-b-app-id"
    app_secret: "replace-with-brand-b-app-secret"
    ad_account_id: "act_222222222222222"
    api_version: "v25.0"
    system_user_id: "replace-with-brand-b-system-user-id"
    facebook_page_id: "replace-with-brand-b-page-id"
    instagram_user_id: "replace-with-brand-b-instagram-user-id"
YAML
chmod 600 "$HOME/.config/meta-ads-cli/environments.yaml"
```

Add one entry beneath `profiles` for every independently authenticated Meta environment. Each
profile has its own app, system-user token, app secret, and ad account. The top-level keys are
`active_profile` and `profiles`; profile names are the keys beneath `profiles`. Lowercase profile
keys shown above are canonical. Numeric `ad_account_id` values are accepted and normalized to
`act_...`; `api_version` defaults to `v25.0` if omitted. Do not commit this file or expose it in
logs. Selection writes are atomic where supported and enforce owner-only (`0600`) file permissions.

A new store **does not automatically select any profile**, even when it contains only one. Inspect
and select one explicitly:

```bash
meta-cli environments list
meta-cli environments current        # exits with guidance until a profile is selected
meta-cli environments use brand-a
meta-cli environments current
meta-cli auth test
```

`list` marks the active profile, `current` shows it, and `use` persists only a name already present
in the store. Add `--json` to any environment command for structured output. Output is restricted to
non-secret identity metadata: name, display name, ad account, API version, and optional actor IDs.
A successful `auth test` also reports the active environment; JSON includes `active_environment` and
`auth_source`.

For an isolated automation or test store:

```bash
export META_CLI_ENVIRONMENTS_FILE="$RUNNER_TEMP/meta-cli/environments.yaml"
```

Create that file with the same schema and `0600` permissions. The override changes only the store
location; it does not select a profile.

The optional `facebook_page_id` and `instagram_user_id` provide defaults when `ads create` omits the
matching flags or YAML values. Explicit command/YAML values take precedence. Existing creative-ID
flows do not use these defaults, and an explicit legacy `instagram_actor_id` prevents injection of
the profile Instagram user ID.

### Legacy auth files and migration

Existing flat auth YAML files remain supported as deliberate per-command overrides. Keep their
uppercase keys (`META_ACCESS_TOKEN`, `META_APP_ID`, `META_APP_SECRET`, `META_AD_ACCOUNT_ID`, and
optional `META_API_VERSION`) and pass the file explicitly:

```bash
meta-cli auth test --config "$HOME/.meta-ads-auth.yaml"
meta-cli campaigns list --auth-config "$HOME/.meta-ads-auth.yaml"
meta-cli ads create --config examples/ad.yaml --auth-config "$HOME/.meta-ads-auth.yaml"
```

An explicit `--config`/`--auth-config` has precedence over the selected named environment. Matching
ambient `META_*` variables may override values in that explicit legacy file. Without an explicit
legacy file, ambient credential variables are ignored and the selected named environment is used.
The legacy path does not borrow Page/Instagram defaults from a selected profile. In `auth test`
output it reports `auth_source: legacy_config` and `active_environment: null`.

To migrate, copy each legacy file's values into a lowercase named profile, leave
`active_profile: null`, inspect with `environments list`, explicitly select with `environments use`,
and validate with `auth test`. Retain or remove the old file according to your secret-rotation and
retention policy.

See the detailed setup and migration guide:

- [`docs/meta-setup-and-configuration.md`](docs/meta-setup-and-configuration.md)

Credentials can be supplied with the existing environment variables / single auth YAML flow, or through a multi-profile environments file for command-center workspaces.

Environment stores use this shape:

```yaml
active_profile: brand-a
profiles:
  brand-a:
    display_name: Brand A
    access_token: "..."
    app_id: "..."
    app_secret: "..."
    ad_account_id: "act_111111111111111"
    api_version: "v25.0"
```

Set `META_CLI_ENVIRONMENTS_FILE=/path/to/.meta-ads-environments.yml` and then use:

```bash
meta-cli environments list      # lists profiles without printing secrets
meta-cli environments current   # shows the selected profile without secrets
meta-cli environments use brand-a
meta-cli auth test
```

When `META_CLI_ENVIRONMENTS_FILE` is set, normal commands load credentials from the selected `active_profile`. Explicit command config files and process environment variables still override those values.

---

## Quick command examples

### Environments and auth

```bash
meta-cli environments list
meta-cli environments current
meta-cli environments use brand-a
meta-cli auth test
meta-cli auth test --json
```

Successful auth tests identify the selected environment in human output. JSON output includes stable
`active_environment` and `auth_source` fields. With an explicit legacy `--config` override,
`active_environment` is `null` and `auth_source` is `legacy_config`; credentials are never shown.

### List objects

```bash
meta-cli campaigns list
meta-cli campaigns get <campaign_id>
meta-cli adsets list --campaign-id <campaign_id>
meta-cli adsets get <adset_id>
meta-cli ads list --adset-id <adset_id>
meta-cli ads list --all
meta-cli ads get <ad_id>
meta-cli creatives get <creative_id>
```

`creatives get` includes the object story spec and asset feed spec, which is useful for confirming
Facebook Page and Instagram actor identities plus placement-specific creative rules.

`campaigns get`, `adsets get`, and `ads get` include Meta delivery diagnostics when available,
including configured/effective status, issues, recommendations, remaining budget, learning-stage
information, review feedback, and failed delivery checks. `adsets get` also includes the
`promoted_object`, including pixel and conversion-event optimization data.

List commands follow every Meta API page by default, so `--limit` controls rows per request rather
than the total rows returned. Use `--max-pages <n>` to cap requests or `--no-paginate` to fetch one
page. To resume from a cursor, pass either `--after <cursor>` or `--before <cursor>` (not both):

```bash
meta-cli campaigns list --limit 100 --max-pages 3
meta-cli ads list --all --no-paginate --after <cursor> --json
```

Human-readable output contains all fetched rows. JSON list output is an envelope with `data` and a
`paging` object containing the requested cursors, `next_after`, `has_more`, `pages_fetched`, and
`total_count` when Meta supplies it. This makes a deliberately capped request resumable.

### Targeting discovery

```bash
meta-cli targeting search-locations --query "Gurugram" --country IN
meta-cli targeting search-locations --query "Noida" --country IN --json
```

Location search returns Meta's targeting key, name, type, country, and region so targeting updates can
use valid platform identifiers instead of guessed city keys.

### Insights

```bash
meta-cli insights ads --all --date-preset last_7d
meta-cli insights ads --adset-id <adset_id> --since 2026-03-01 --until 2026-03-21
meta-cli insights ads --all --output-file exports/insights.csv --output-format csv
```

Ad insights are also fully paginated by default and support `--limit`, `--max-pages`,
`--no-paginate`, `--after`, and `--before`. Both dates are required when using `--since` and
`--until`; an explicit date range takes precedence over `--date-preset`. `--json` and JSON exports
use the same `data`/`paging` envelope. CSV exports contain the fetched insight rows only.

### First-class recurring account report

`report account` replaces one-off SDK reporting scripts. It collects current account metadata,
campaigns, ad sets, ads, and account-level insights in one read-only workflow; it never changes ad
account objects. By default it includes today, yesterday, trailing 7-day, trailing 30-day, and
lifetime (`maximum`) Meta date presets. It uses the standard CLI credentials, or a YAML path passed
with `--auth-config`.

```bash
# Human-readable account, entity, and period summaries
meta-cli report account

# Complete structured report suitable for a daily archive (parent directories are created)
meta-cli report account --output-file "reports/$(date +%F)-account.json"

# Select periods and emit the complete report to stdout
meta-cli report account --periods today,7d,30d --json

# Safely use a local auth file without putting any credential values in the command
meta-cli report account --auth-config "$HOME/.meta-ads-auth.yaml" --output-file reports/account.json
```

The complete JSON includes `generated_at`, `read_only`, `account`, `campaigns`, `adsets`, `ads`, an
entity `summary`, and one `insights` entry per requested period. The normal terminal view is a
concise summary; use `--json` or `--output-file` for full entity data. Entity collections are fully
paginated by default, and `--limit` is the per-request page size. Use `--max-pages` only when
intentionally limiting each entity collection in a large account snapshot. Account-level insight
rows are fully paginated independently.

### Media uploads

```bash
meta-cli media upload-image ./creative.jpg
meta-cli media upload-video ./creative.mp4
```

### Create flows

```bash
meta-cli campaigns create --config examples/campaign.yaml
meta-cli campaigns create --name "Traffic Campaign" --objective OUTCOME_TRAFFIC --dry-run --json
meta-cli adsets create --config examples/adset.yaml
meta-cli adsets update-targeting <adset_id> --targeting-file examples/adset.yaml --yes
meta-cli ads create --config examples/ad.yaml
meta-cli ads create --config examples/ad-placement-images.yaml --dry-run --json
meta-cli ads update-creative <ad_id> --creative-id <creative_id> --yes
```

Campaign creation requires `name` and `objective`. It accepts optional campaign-level
`daily_budget` or `lifetime_budget`, and `special_ad_categories` as a YAML list or a comma-separated
`--special-ad-categories` flag. For campaigns whose budget lives on ad sets, current Meta API
versions require `is_adset_budget_sharing_enabled`; set it in YAML or use
`--adset-budget-sharing` / `--no-adset-budget-sharing`. `buying_type`, `special_ad_categories`, and
`status` default to `AUCTION`, `[]`, and `PAUSED`, respectively. Use `--dry-run` to validate and
inspect the exact payload without loading credentials or making a Meta SDK request; add `--json`
for machine-readable output.

Ad-set creation accepts `is_dynamic_creative: true` in YAML or `--dynamic-creative` on the command
line. Enable it when ads under that ad set will use an `asset_feed_spec` with multiple images,
headlines, bodies, or descriptions. Meta requires dynamic-creative ads to be created under a
dynamic-creative ad set, and this setting should be chosen when the ad set is created. The flag is
optional, so existing non-dynamic ad-set behavior is unchanged.

For Instagram delivery, set `instagram_user_id` in ad YAML or pass `--instagram-user-id`; use the
legacy `instagram_actor_id` / `--instagram-actor-id` only for accounts that still expose an actor
ID. If ad YAML or command flags omit `page_id` / `--page-id` and the Instagram identity, `ads create`
uses the selected named profile's optional `facebook_page_id` and `instagram_user_id`. Explicit ad
values take precedence, including an explicit legacy Instagram actor ID. Supplying `--auth-config`
is a deliberate legacy override and therefore does not borrow identity defaults from the selected
profile. If no explicit or profile Facebook Page ID is available, the existing validation error is
preserved. `creatives get` shows the identity field used by an existing working creative.

For placement-specific static creative, `ads create` accepts `image_assets` and
`asset_customization_rules` in YAML. Each image asset has a Meta image `hash` and a unique,
nonblank `label`; each rule has a Meta `customization_spec`, an `image_label` referencing one of
those labels, and an optional `priority`. The generated `asset_feed_spec` adds the label as an
`adlabels` entry on each image and emits the rules with Meta's `{\"name\": ...}` image-label
shape. See `examples/ad-placement-images.yaml` for dedicated 4:5 feed, 1:1, and 9:16
Stories/Reels assets.

The equivalent CLI flags accept JSON arrays:

```bash
meta-cli ads create \
  --adset-id "$ADSET_ID" --name "Placement images" --page-id "$PAGE_ID" \
  --destination-url "https://example.com" --bodies "Find the right tutor" \
  --image-assets-json '[{"hash":"hash_4x5","label":"feed_4x5"},{"hash":"hash_1x1","label":"square_1x1"},{"hash":"hash_9x16","label":"stories_9x16"}]' \
  --asset-customization-rules-json '[{"customization_spec":{"publisher_platforms":["facebook","instagram"],"facebook_positions":["feed"],"instagram_positions":["stream"]},"image_label":"feed_4x5","priority":1}]' \
  --dry-run --json
```

`image_assets` requires at least one customization rule, and customization rules cannot be used
without `image_assets`. Blank or duplicate asset labels and rules that reference unknown labels
are rejected. Meta API v22+ no longer supports segment asset customization for multiple text
variants, so placement rules accept at most one headline, body, and description. For multiple copy
variants plus several uploaded image ratios, use `image_hashes` without
`asset_customization_rules`; Meta then optimizes the asset-feed combinations. `image_hashes` and
`image_assets` are mutually exclusive. Existing `image_hashes` behavior is unchanged, including
the single-image story payload and multi-image asset-feed payload.

`adsets update-targeting` replaces the complete targeting object, so first export or retain the
existing targeting and include every constraint and placement that must remain. Supply exactly one
of `--targeting-json` or `--targeting-file`; a JSON/YAML file may contain the targeting object
itself or an ad set config with a top-level `targeting` key. The command requires confirmation
unless `--yes` is passed and supports `--dry-run`.

### Status control

```bash
meta-cli campaigns pause <campaign_id>
meta-cli campaigns resume <campaign_id>
meta-cli adsets pause <adset_id>
meta-cli adsets resume <adset_id>
meta-cli ads pause <ad_id>
meta-cli ads resume <ad_id>
```

---

## YAML examples

- `examples/campaign.yaml`
- `examples/adset.yaml`
- `examples/ad.yaml`
- `examples/ad-placement-images.yaml`

Use returned media IDs in ad config:

- image upload → `image_hashes`, or `image_assets[].hash` for placement-specific images
- video upload → `video_id`

---

## Safety notes

- New campaigns, ad sets, and ads default to `PAUSED`
- Use `--dry-run` before real create/update operations
- Pause/resume requires confirmation unless `--yes` is passed
- Validate auth (`meta-cli auth test`) before operations

---

## Troubleshooting

### Auth test fails

Check:

- token validity
- account permissions
- app id/secret correctness
- account ID format

### Unsupported field combinations

Meta may reject combinations of objective, optimization goal, billing event, targeting, or creative fields. The CLI surfaces API errors directly.

### Homebrew install issues

Ensure:

- tap repo is added: `brew tap stuntcoders/meta-ads-cli`
- install command uses full formula reference: `brew install stuntcoders/meta-ads-cli/meta-ads-cli`
- formula exists in tap repo at `Formula/meta-ads-cli.rb`
- your tap formula is up to date (newer generated formulas include `rust` as a build dependency for `pydantic-core`)

### pipx install issues

Ensure:

- `pipx` is installed and path is initialized (`python3 -m pipx ensurepath`)
- you use the full Git URL: `git+https://github.com/stuntcoders/meta_ads_cli.git`

---

## Development

Use Python 3.12 and install the exact development dependency set for repeatable validation:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make install-lock
make lint
make test
python -m build
```

Builds write the source distribution and wheel to `dist/`; inspect both archives before publishing.

`requirements.in` and `requirements-dev.in` are the production and development dependency inputs.
Their generated locks must stay synchronized: `requirements-dev.lock` includes the exact production
pins from `requirements.lock`. Regenerate both with Python 3.12 after changing either input:

```bash
python -m pip install "pip-tools>=7.4.1"
make lock
git diff -- requirements.lock requirements-dev.lock
```

Audit both lock files in an isolated environment before release (install `pip-audit` only in that
environment, not as an application dependency):

```bash
AUDIT_DIR="$(mktemp -d)"
python3.12 -m venv "$AUDIT_DIR/venv"
source "$AUDIT_DIR/venv/bin/activate"
python -m pip install --upgrade pip pip-audit
python -m pip_audit -r requirements.lock
python -m pip_audit -r requirements-dev.lock
deactivate
rm -rf "$AUDIT_DIR"
```

Project layout:

- `src/meta_cli/` — app, commands, sdk, schemas
- `tests/` — mocked unit tests + optional integration tests
- `examples/` — YAML examples
- `docs/meta-setup-and-configuration.md` — Meta setup + credential configuration guide
- `scripts/` — build/release helpers
- `.github/workflows/` — release + Homebrew automation
- `AGENTS.md` — coding-agent operating instructions

### Release and Homebrew automation

Run **Release and Publish** manually in GitHub Actions. Supply the version and source branch; by
default the workflow validates with Ruff and pytest, updates `pyproject.toml` and
`src/meta_cli/__init__.py`, pushes the version commit and tag, and publishes a GitHub release. A
published release triggers **Homebrew Formula PR**, which generates formula resources from the
production `requirements.lock` and opens a pull request in the tap repository.

Configure these GitHub repository settings before releasing:

- Secret `HOMEBREW_TAP_TOKEN` — a token that can read and push branches to the tap repository and
  open pull requests there.
- Variable `HOMEBREW_TAP_REPO` — required tap repository in `owner/repository` form.
- Variables `HOMEBREW_FORMULA_NAME`, `HOMEBREW_FORMULA_PATH`, and
  `HOMEBREW_TAP_BASE_BRANCH` — optional overrides; defaults are `meta-ads-cli`,
  `Formula/meta-ads-cli.rb`, and the tap repository's default branch.

The tap repository must already have an initial commit and default branch. The release workflow can
also create a draft or prerelease, skip its version-file bump, or skip validation through explicit
workflow inputs. The Homebrew workflow can be rerun manually for a release tag and optional tap
repository override.

For production workflows, create in `PAUSED`, verify in Ads Manager, then explicitly resume.

# Meta Ads CLI (`meta-cli`)

Production-grade Python CLI for managing Meta ads with the **official Meta Python Business SDK**.

## Features

- ✅ Auth/config validation (`meta-cli auth test`)
- ✅ Campaign/Ad Set/Ad hierarchy support
- ✅ List campaigns, ad sets, ads (scoped or account-wide)
- ✅ Fetch ad insights/performance metrics
- ✅ Upload image/video assets
- ✅ Create ad sets from YAML or flags
- ✅ Create ads from YAML or flags
- ✅ Supports multi-text creative path (asset feed spec) when applicable
- ✅ Pause/resume campaigns, ad sets, ads with confirmations
- ✅ `--dry-run` for create/status operations
- ✅ JSON output mode for automation (`--json`)

---

## Requirements

- Python 3.12+
- Meta Ads account access with required permissions
- Valid Meta access token

---

## Meta setup (step-by-step, first-time users)

If you are new to Meta APIs, complete this checklist before running the CLI.

### 1) Confirm business + ad account access

In **Meta Business Manager** (`business.facebook.com`):

1. Open **Business Settings**.
2. Confirm your business owns (or has partner access to) the target ad account.
3. Confirm the operator/system user you will use has ad account permissions (at minimum to read; for creation/update, manage-level permissions are required).

### 2) Create a Meta App and enable Marketing API

In **Meta for Developers** (`developers.facebook.com`):

1. Create an app (Business type recommended for production).
2. Add the **Marketing API** product.
3. Collect:
   - **App ID** → `META_APP_ID`
   - **App Secret** → `META_APP_SECRET`

### 3) Generate an access token (recommended: System User token)

Recommended production path:

1. In **Business Settings** → **Users** → **System Users**, create/select a system user.
2. Assign assets to that system user:
   - Ad Account (with required level, usually Manage Campaigns for write actions)
   - Facebook Page if page-backed ads are used
3. Generate token for your app with required scopes.

Minimum commonly needed scopes:

- `ads_read` (listing/reporting)
- `ads_management` (create/update/pause/resume)

Depending on workflow/account setup, Meta may also require additional scopes such as page/business related permissions.

Set generated token as:

- `META_ACCESS_TOKEN`

### 4) Get your Ad Account ID

You can get this from Ads Manager URL or Business Settings.

- Raw numeric ID is accepted (CLI normalizes to `act_<id>`)
- Or pass it directly as `act_<id>`

Set as:

- `META_AD_ACCOUNT_ID`

### 5) (Optional) Choose API version

Set:

- `META_API_VERSION` (defaults to `v20.0` if omitted)

### 6) Export environment variables

```bash
export META_ACCESS_TOKEN="..."
export META_APP_ID="..."
export META_APP_SECRET="..."
export META_AD_ACCOUNT_ID="act_1234567890"
# optional
export META_API_VERSION="v20.0"
```

### 7) Verify credentials before running any action

```bash
meta-cli auth test
```

If this fails, the rest of the CLI will fail too. Fix auth/access first.

### 8) Additional IDs needed for ad creation workflows

For creating ads/creatives you may also need:

- `page_id` (Facebook Page ID)
- `instagram_actor_id` (if using IG placement identity)
- Uploaded media IDs/hashes:
  - image upload returns image hash
  - video upload returns video id

---

## Installation

### Local install (current machine)

```bash
python3 -m pip install .
```

For development:

```bash
python3 -m pip install ".[dev]"
```

For reproducible local environments (pinned dependencies):

```bash
python3 -m pip install -r requirements-dev.lock
```

You can refresh lock files with:

```bash
make lock
```

### Global install for your team (recommended: `pipx`)

`pipx` installs the CLI globally while isolating dependencies per app.
This works across macOS, Linux, and Windows (with Python 3.12+ available).

#### Option A: Install globally from your Git repository (best for internal teams)

```bash
pipx install "git+https://<your-git-host>/<org>/<repo>.git"
```

Pin to a tag/release:

```bash
pipx install "git+https://<your-git-host>/<org>/<repo>.git@v0.1.0"
```

Upgrade later:

```bash
pipx upgrade meta-ads-cli
```

#### Option B: Install globally from a built wheel

Maintainer builds artifacts:

```bash
./scripts/build_artifacts.sh
```

Team installs wheel globally:

```bash
pipx install ./dist/meta_ads_cli-<version>-py3-none-any.whl
```

You can also host the wheel and install via URL:

```bash
pipx install "https://<artifact-host>/meta_ads_cli-<version>-py3-none-any.whl"
```

### Homebrew tap formula (direct `brew install`, macOS)

If you want your team to install with native Homebrew commands, use a tap repository.

#### Maintainer: one-time setup

1. Create a separate tap repo named like: `homebrew-meta-ads-cli`
2. Inside it, keep formulas under `Formula/`

#### Maintainer: per release

1. Publish a source release tarball URL for the tagged version (example: `v0.1.0`).
2. Compute its SHA256:

```bash
curl -L "https://github.com/<org>/<repo>/archive/refs/tags/v0.1.0.tar.gz" -o /tmp/meta-ads-cli-v0.1.0.tar.gz
shasum -a 256 /tmp/meta-ads-cli-v0.1.0.tar.gz
```

3. Generate the Homebrew formula using this repository's lockfile:

```bash
scripts/release_brew_formula.sh \
  --homepage "https://github.com/<org>/<repo>" \
  --source-url "https://github.com/<org>/<repo>/archive/refs/tags/v0.1.0.tar.gz" \
  --source-sha256 "<sha256_from_previous_step>" \
  --output "/path/to/homebrew-meta-ads-cli/Formula/meta-ads-cli.rb"
```

4. Commit and push the updated formula in the tap repo.

#### Team usage

```bash
brew tap <org>/meta-ads-cli
brew install meta-ads-cli
meta-cli --help
```

Upgrade later:

```bash
brew update
brew upgrade meta-ads-cli
```

#### Optional automation: open tap PR automatically on each release

This repository includes `.github/workflows/homebrew-formula-pr.yml`.

When a GitHub Release is published (or via manual workflow dispatch), it will:

1. Build source archive URL for the release tag
2. Compute source SHA256
3. Generate `Formula/meta-ads-cli.rb`
4. Open a pull request in your tap repository

Required setup in this source repository:

- Tap repository is initialized with at least one commit and a default branch
  - Example: create `README.md` in `stuntcoders/homebrew-meta-ads-cli` on `main`
- Repository **secret**: `HOMEBREW_TAP_TOKEN`
  - Use a PAT or GitHub App token with write access to the tap repo
  - Needs permissions to push branches and open PRs in tap repo
- Repository **variable**: `HOMEBREW_TAP_REPO`
  - Example: `your-org/homebrew-meta-ads-cli`

Optional repository variables:

- `HOMEBREW_FORMULA_NAME` (default: `meta-ads-cli`)
- `HOMEBREW_FORMULA_PATH` (default: `Formula/meta-ads-cli.rb`)
- `HOMEBREW_TAP_BASE_BRANCH` (optional override; if omitted, workflow uses tap repo default branch)

You can also run the workflow manually and override `tag` and `tap_repo` inputs.

Important for manual runs: always provide `tag` (for example `v0.1.0`).
If omitted, the workflow may fail because it cannot resolve a release tarball URL.

Workflow diagnostics include:

- resolved tag/source URL output
- tap repository access validation (with explicit HTTP error body)
- source download failure details

If the workflow fails, open the failed run and inspect the first red step:

- `Resolve workflow configuration`
- `Validate tap repository access`
- `Compute source archive SHA256`
- `Create pull request in tap repository`

Note: GitHub may display Node runtime deprecation warnings for marketplace actions. Those warnings are informational unless they explicitly fail a step.

### Brew + pipx fallback (easiest operationally)

If you prefer not to maintain a tap formula, this is the simplest macOS path:

```bash
brew install python@3.12 pipx
pipx ensurepath
pipx install "git+https://<your-git-host>/<org>/<repo>.git@v0.1.0"
```

---

## Configuration

The CLI reads credentials from environment variables and supports optional auth YAML overrides.

### Environment variables

Copy `.env.example` and fill values:

- `META_ACCESS_TOKEN`
- `META_APP_ID`
- `META_APP_SECRET`
- `META_AD_ACCOUNT_ID` (numeric or `act_...`)
- `META_API_VERSION` (optional, default `v20.0`)

Example:

```bash
export META_ACCESS_TOKEN="..."
export META_APP_ID="..."
export META_APP_SECRET="..."
export META_AD_ACCOUNT_ID="act_1234567890"
```

### Validate auth

```bash
meta-cli auth test
meta-cli auth test --json
meta-cli auth test --config ./auth.yaml
```

Most commands also accept `--auth-config <path>` when you prefer file-based credentials over environment variables.

---

## Meta Object Hierarchy

The CLI follows Meta's object hierarchy:

`Campaign -> Ad Set -> Ad Creative -> Ad`

- Campaigns are the top-level budget/objective containers.
- Ad sets define budget schedule, optimization, and targeting.
- Creatives define the text/media payload.
- Ads bind creatives to ad sets and serve delivery status.

---

## Command Reference

### Campaigns

```bash
meta-cli campaigns list
meta-cli campaigns list --json --after <cursor> --no-paginate
meta-cli campaigns pause <campaign_id>
meta-cli campaigns resume <campaign_id>
```

### Ad Sets

```bash
meta-cli adsets list --campaign-id <campaign_id>
meta-cli adsets list --campaign-id <campaign_id> --json --after <cursor> --max-pages 1
meta-cli adsets create --config examples/adset.yaml
meta-cli adsets create --campaign-id <id> --name "Test" --daily-budget 5000 --targeting-json '{"geo_locations":{"countries":["US"]}}'
meta-cli adsets pause <adset_id>
meta-cli adsets resume <adset_id>
```

### Ads

```bash
meta-cli ads list --adset-id <adset_id>
meta-cli ads list --all
meta-cli ads list --all --json --after <cursor> --no-paginate
meta-cli ads create --config examples/ad.yaml
meta-cli ads pause <ad_id>
meta-cli ads resume <ad_id>
```

Common pagination flags for list/reporting commands:

- `--after <cursor>` / `--before <cursor>`
- `--paginate` / `--no-paginate`
- `--max-pages <n>`

### Insights

```bash
meta-cli insights ads --all --date-preset last_7d
meta-cli insights ads --adset-id <id> --since 2026-03-01 --until 2026-03-21
meta-cli insights ads --all --json --after <cursor> --no-paginate
meta-cli insights ads --all --output-file exports/insights.json --output-format json
meta-cli insights ads --all --output-file exports/insights.csv --output-format csv
```

Metrics include (when returned by API):

- impressions
- reach
- clicks
- inline link clicks
- ctr
- cpc
- spend
- actions/conversions
- cost per result

JSON output for list/insights commands now includes a `paging` object (for example `next_after`) to support machine-driven pagination.

Insights also supports custom action mappings:

- `--result-action-types` (what counts as conversions)
- `--cost-action-types` (which action drives cost-per-result)

### Media

```bash
meta-cli media upload-image ./creative.jpg
meta-cli media upload-video ./creative.mp4
meta-cli media upload-video ./creative.mp4 --wait --poll-interval 5 --timeout 1800
meta-cli media upload-video ./creative.mp4 --no-wait
```

`upload-video` now tracks processing progress in the terminal (non-JSON mode) until Meta reports completion.
By default it waits for processing (`--wait`); use `--no-wait` to return immediately after upload.
In `--json` mode, the response includes a `processing` object when waiting is enabled.

Use the returned `image_hash` (images) or `id` (videos) in ad creation config (`image_hashes` / `video_id`).

---

## YAML Config Examples

- `examples/adset.yaml`
- `examples/ad.yaml`

Use these as templates for real operator workflows.

---

## Safety Notes

- Ad sets and ads default to `PAUSED`.
- Pause/resume commands prompt for confirmation unless `--yes` is provided.
- Use `--dry-run` to validate payloads before making API calls.
- Prefer testing in non-production campaigns first.

---

## Troubleshooting

### Missing credentials

You will get a validation error listing required env keys.

### Invalid token / permissions

`meta-cli auth test` will fail with a Meta API error. Verify:

- token validity
- ads_management permissions
- account access scope

### Unsupported field combinations

Meta may reject combinations of objective, optimization goal, billing event, or creative fields. The CLI surfaces the SDK/API error directly.

### Dynamic creative / multi-text notes

Multi-headline/body flows use `asset_feed_spec`. Some combinations require ad set settings (for example dynamic creative compatibility) and may be rejected depending on account setup/objective.

---

## Development

```bash
make lint
make test
```

Generate formula with Make:

```bash
make brew-formula \
  HOMEPAGE="https://github.com/<org>/<repo>" \
  SOURCE_URL="https://github.com/<org>/<repo>/archive/refs/tags/v0.1.0.tar.gz" \
  SOURCE_SHA256="<sha256>" \
  OUTPUT="/path/to/homebrew-meta-ads-cli/Formula/meta-ads-cli.rb"
```

Optional live integration check:

```bash
LIVE_META_TESTS=1 python3 -m pytest tests/integration
```

This runs a real `auth test` flow and requires valid Meta env credentials.

Project layout:

- `src/meta_cli/` — CLI app, SDK client, schemas, commands
- `tests/` — mocked tests (no live Meta credentials required)
- `examples/` — ad set/ad YAML examples
- `scripts/build_artifacts.sh` — build wheel/sdist for distribution
- `scripts/generate_brew_formula.py` — generate Homebrew formula from pinned lockfile
- `scripts/release_brew_formula.sh` — helper wrapper for release-time formula generation
- `.github/workflows/homebrew-formula-pr.yml` — automated PR flow to Homebrew tap repo
- `requirements*.in` / `requirements*.lock` — reproducible dependency inputs + lockfiles
- `LICENSE` — project license (MIT)

---

## Important Operational Guidance

For production campaigns, create new entities in `PAUSED`, verify tracking/creative/targeting in Ads Manager, then explicitly resume.

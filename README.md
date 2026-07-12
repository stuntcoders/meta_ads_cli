# Meta Ads CLI (`meta-cli`)

Production-grade Python CLI for managing Meta ads with the **official Meta Python Business SDK**.

## What this CLI does

- Validate Meta auth and account access
- List campaigns, ad sets, ads
- Fetch ad insights/performance metrics
- Save read-only account snapshots with recurring period insights
- Upload image/video assets
- Create campaigns, ad sets, and ads from YAML or flags
- Pause/resume campaigns, ad sets, ads
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

See full configuration details in:

- [`docs/meta-setup-and-configuration.md`](docs/meta-setup-and-configuration.md)

---

## Quick command examples

### Auth

```bash
meta-cli auth test
meta-cli auth test --json
```

### List objects

```bash
meta-cli campaigns list
meta-cli campaigns get <campaign_id>
meta-cli adsets list --campaign-id <campaign_id>
meta-cli adsets get <adset_id>
meta-cli ads list --adset-id <adset_id>
meta-cli ads list --all
meta-cli ads get <ad_id>
```

`adsets get` details include the `promoted_object`, including pixel and conversion-event
optimization data returned by Meta, in both normal and JSON output.

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
meta-cli ads create --config examples/ad.yaml
meta-cli ads create --config examples/ad-placement-images.yaml --dry-run --json
meta-cli ads update-creative <ad_id> --creative-id <creative_id> --yes
```

Campaign creation requires `name` and `objective`. It accepts optional campaign-level
`daily_budget` or `lifetime_budget`, and `special_ad_categories` as a YAML list or a comma-separated
`--special-ad-categories` flag. `buying_type`, `special_ad_categories`, and `status` default to
`AUCTION`, `[]`, and `PAUSED`, respectively. Use `--dry-run` to validate and inspect the exact
payload without loading credentials or making a Meta SDK request; add `--json` for machine-readable
output.

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
are rejected. `image_hashes` and `image_assets` are mutually exclusive. Existing
`image_hashes` behavior is unchanged, including the single-image story payload and multi-image
asset-feed payload.

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

```bash
make lint
make test
```

Project layout:

- `src/meta_cli/` — app, commands, sdk, schemas
- `tests/` — mocked unit tests + optional integration tests
- `examples/` — YAML examples
- `docs/meta-setup-and-configuration.md` — Meta setup + credential configuration guide
- `scripts/` — build/release helpers
- `.github/workflows/` — release + Homebrew automation
- `AGENTS.md` — coding-agent operating instructions

For production workflows, create in `PAUSED`, verify in Ads Manager, then explicitly resume.

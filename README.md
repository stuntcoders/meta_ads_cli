# Meta Ads CLI (`meta-cli`)

Production-grade Python CLI for managing Meta ads with the **official Meta Python Business SDK**.

## What this CLI does

- Validate Meta auth and account access
- List campaigns, ad sets, ads
- Fetch ad insights/performance metrics
- Upload image/video assets
- Create ad sets and ads from YAML or flags
- Pause/resume campaigns, ad sets, ads

---

## Prerequisites

- Python 3.12+
- A Meta app with Marketing API access
- Meta ad account access with required permissions
- Valid Meta access token

---

## Meta setup (first-time users)

If this is your first time using Meta APIs, complete these steps first.

### 1) Confirm business and ad account access

In `business.facebook.com`:

1. Open **Business Settings**
2. Confirm your business owns (or has partner access to) the target ad account
3. Confirm the user/system user has required ad account permissions

### 2) Create Meta app and enable Marketing API

In `developers.facebook.com`:

1. Create an app (Business type recommended)
2. Add **Marketing API** product
3. Copy:
   - App ID → `META_APP_ID`
   - App Secret → `META_APP_SECRET`

### 3) Generate access token

Recommended: system user token from Business Settings.

Typical required scopes:

- `ads_read`
- `ads_management`

Set token as `META_ACCESS_TOKEN`.

### 4) Get ad account ID

Set `META_AD_ACCOUNT_ID` using either:

- numeric ID (CLI normalizes to `act_<id>`), or
- direct `act_<id>`

### 5) Export env vars and validate

```bash
export META_ACCESS_TOKEN="..."
export META_APP_ID="..."
export META_APP_SECRET="..."
export META_AD_ACCOUNT_ID="act_1234567890"
# optional
export META_API_VERSION="v20.0"

meta-cli auth test
```

---

## Installation

## 1) Local install (from source repo)

Repository URL:

- `https://github.com/stuntcoders/meta_ads_cli`

Install:

```bash
git clone https://github.com/stuntcoders/meta_ads_cli.git
cd meta_ads_cli
python3 -m pip install .
```

Verify:

```bash
meta-cli --help
```

For development install:

```bash
python3 -m pip install -e ".[dev]"
```

## 2) Homebrew install (recommended for team machines)

Tap repository URL:

- `https://github.com/stuntcoders/homebrew-meta-ads-cli`

Install:

```bash
brew tap stuntcoders/meta-ads-cli
brew install meta-ads-cli
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

---

## Configuration

Required environment variables:

- `META_ACCESS_TOKEN`
- `META_APP_ID`
- `META_APP_SECRET`
- `META_AD_ACCOUNT_ID`
- `META_API_VERSION` (optional, default `v20.0`)

You can also pass optional auth config file paths where supported:

```bash
meta-cli auth test --config ./auth.yaml
```

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
meta-cli adsets list --campaign-id <campaign_id>
meta-cli ads list --adset-id <adset_id>
meta-cli ads list --all
```

### Insights

```bash
meta-cli insights ads --all --date-preset last_7d
meta-cli insights ads --adset-id <id> --since 2026-03-01 --until 2026-03-21
meta-cli insights ads --all --output-file exports/insights.csv --output-format csv
```

### Media uploads

```bash
meta-cli media upload-image ./creative.jpg
meta-cli media upload-video ./creative.mp4
```

### Create flows

```bash
meta-cli adsets create --config examples/adset.yaml
meta-cli ads create --config examples/ad.yaml
```

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

- `examples/adset.yaml`
- `examples/ad.yaml`

Use returned media IDs in ad config:

- image upload → `image_hashes`
- video upload → `video_id`

---

## Safety notes

- New ad sets/ads default to `PAUSED`
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
- formula exists in tap repo at `Formula/meta-ads-cli.rb`

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
- `scripts/` — build/release helpers
- `.github/workflows/` — release + Homebrew automation
- `AGENTS.md` — coding-agent operating instructions

For production workflows, create in `PAUSED`, verify in Ads Manager, then explicitly resume.

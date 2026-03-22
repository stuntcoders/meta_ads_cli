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

## Installation

```bash
python3 -m pip install .
```

For development:

```bash
python3 -m pip install ".[dev]"
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
meta-cli campaigns pause <campaign_id>
meta-cli campaigns resume <campaign_id>
```

### Ad Sets

```bash
meta-cli adsets list --campaign-id <campaign_id>
meta-cli adsets create --config examples/adset.yaml
meta-cli adsets create --campaign-id <id> --name "Test" --daily-budget 5000 --targeting-json '{"geo_locations":{"countries":["US"]}}'
meta-cli adsets pause <adset_id>
meta-cli adsets resume <adset_id>
```

### Ads

```bash
meta-cli ads list --adset-id <adset_id>
meta-cli ads list --all
meta-cli ads create --config examples/ad.yaml
meta-cli ads pause <ad_id>
meta-cli ads resume <ad_id>
```

### Insights

```bash
meta-cli insights ads --all --date-preset last_7d
meta-cli insights ads --adset-id <id> --since 2026-03-01 --until 2026-03-21
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

### Media

```bash
meta-cli media upload-image ./creative.jpg
meta-cli media upload-video ./creative.mp4
```

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

Optional live integration check:

```bash
LIVE_META_TESTS=1 python3 -m pytest tests/integration
```

This runs a real `auth test` flow and requires valid Meta env credentials.

Project layout:

- `src/meta_cli/` — CLI app, SDK client, schemas, commands
- `tests/` — mocked tests (no live Meta credentials required)
- `examples/` — ad set/ad YAML examples

---

## Important Operational Guidance

For production campaigns, create new entities in `PAUSED`, verify tracking/creative/targeting in Ads Manager, then explicitly resume.

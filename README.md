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

## Meta setup and configuration

Full setup/configuration guide:

- [`docs/meta-setup-and-configuration.md`](docs/meta-setup-and-configuration.md)

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

## 3) pipx install (global, isolated Python env)

`pipx` is a good alternative when you do not want Homebrew-managed formula updates.

If `pipx` is not installed:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Install from repository:

```bash
pipx install "git+https://github.com/stuntcoders/meta_ads_cli.git"
```

Install pinned release:

```bash
pipx install "git+https://github.com/stuntcoders/meta_ads_cli.git@v0.1.0"
```

Upgrade later:

```bash
pipx upgrade meta-ads-cli
```

Local maintainers can also run:

```bash
make install-pipx-local
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

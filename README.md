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
- List/create account labels and add an existing label to one ad or campaign without replacing other labels
- Archive one non-delivering ad with read-only preflight and verified readback (not deletion)
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

For a process-local read or automation command that must not change the persisted selection, set an
exact profile name with `META_CLI_ENVIRONMENT`:

```bash
META_CLI_ENVIRONMENT=brand-b meta-cli insights ads --all --json
```

This override selects credentials only for that process, never rewrites `active_profile`, and fails
closed when the profile is absent or malformed. Do not treat it as reusable authorization for
scheduled mutations; mutation workflows still require their normal confirmation, dry-run, and
readback controls.

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
meta-cli custom-conversions list
meta-cli custom-conversions get <custom_conversion_id>
```

`creatives get` includes the object story spec, asset feed spec, and `url_tags`. These fields are
useful for confirming Facebook Page and Instagram actor identities, placement-specific creative
rules, and URL-parameter templates such as Meta's dynamic campaign, ad set, and ad IDs.

`campaigns get`, `adsets get`, and `ads get` include Meta delivery diagnostics when available,
including configured/effective status, issues, recommendations, remaining budget, learning-stage
information, review feedback, and failed delivery checks. `adsets get` also includes the
`promoted_object`, including pixel and conversion-event optimization data. Custom-conversion reads
include the event source, rule, category, availability, and first/last fired timestamps when Meta
supplies them.

For read-only label and delivery verification, `ads get` and `campaigns get` request
`account_id`, `id`, `name`, `status`, `configured_status`, `effective_status`, and `adlabels`.
Ad details also include `adset_id` and `campaign_id`; campaign details include `daily_budget`,
`lifetime_budget`, and `budget_remaining` (raw minor currency units, when applicable).
Existing creative and diagnostic fields remain available. JSON is the returned object, without
an envelope: omitted optional fields stay omitted and an empty `adlabels` list stays empty.
The SDK may omit null-valued fields during export; any nulls retained in its returned dictionary
remain null in JSON. A missing label field is not proof that there are no labels.
Human-readable output leaves unavailable values blank.

```bash
meta-cli environments list --json
meta-cli environments current --json  # persistent selection, not the process override
# Use an exact configured environment name; this override does not change active_profile.
META_CLI_ENVIRONMENT=<environment_name> meta-cli ads get <ad_id> --json
META_CLI_ENVIRONMENT=<environment_name> meta-cli campaigns get <campaign_id> --json
```

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

### Labels/archive command reference

| Command syntax | Required input | Additional options |
| --- | --- | --- |
| `meta-cli labels list` | None | `--limit`, `--after`, `--before`, `--paginate` / `--no-paginate`, `--max-pages` |
| `meta-cli labels create --name "Winner"` | `--name TEXT` | `--dry-run`, `--yes` / `-y` |
| `meta-cli ads add-label <ad_id> --label-id <label_id>` | One ad ID and `--label-id TEXT` | `--dry-run`, `--yes` / `-y` |
| `meta-cli campaigns add-label <campaign_id> --label-id <label_id>` | One campaign ID and `--label-id TEXT` | `--dry-run`, `--yes` / `-y` |
| `meta-cli ads archive <ad_id>` | One ad ID | `--dry-run`, `--yes` / `-y` |
| `meta-cli ads get <ad_id>` | One ad ID | None |
| `meta-cli campaigns get <campaign_id>` | One campaign ID | None |

All seven commands also accept `--json`, `--help`, and `--auth-config PATH` (the deliberate
[legacy auth override](#legacy-auth-files-and-migration), not an object configuration file).
Named environments are recommended; command-center workspaces should use their repository wrapper
`./bin/meta-cli` instead of the global executable and should not use legacy auth overrides.
There is no `--environment` flag: `META_CLI_ENVIRONMENT` takes an exact configured profile name.
Replace angle-bracket placeholders before running examples; they are not literal shell arguments.

For `labels list`, `--limit INTEGER` defaults to **50**, accepts **1–500**, and is a page size,
not a total-result limit. `--paginate` is enabled by default; `--no-paginate` fetches one page.
`--max-pages INTEGER` must be at least **1** and defaults to no cap. `--after TEXT` and
`--before TEXT` default to unset and are mutually exclusive. Creation/application safety reads
always scan the complete account label inventory; those mutation commands have no pagination flags.

`--dry-run`, `--yes`/`-y`, and `--json` default to false. Dry runs for these mutations require
credentials and make read-only Meta requests; **they are not offline validation** and never send
SDK `validate_only` writes. No-op/dry-run paths do not prompt; actual writes require confirmation
unless `--yes`/`-y` is passed. `--json` alone does not suppress confirmation. Use `--yes --json`
only after authorizing the exact write. Declining confirmation or sending EOF exits nonzero.

Before account work, inspect `environments list` and `environments current`; select a profile only
when explicitly intended. Re-check persistent selection immediately before each live mutation.
When using a process override, verify that exact profile in the list: `environments current` still
reports the persisted selection. Mutation results identify the actual `environment` and normalized
`account_id`; plain `ads get`/`campaigns get` return object data without environment metadata and do
not perform the mutation commands' ownership/preflight checks.

### Account labels

Account adlabels are reusable IDs for organizing ads/campaigns, not creative asset-feed placement
labels. These commands operate only in the configured account; they do not apply labels to objects.

```bash
# Read-only list; supports the standard pagination flags described above.
META_CLI_ENVIRONMENT=<environment_name> meta-cli labels list --json
META_CLI_ENVIRONMENT=<environment_name> meta-cli labels list --no-paginate --limit 50 --json

# Preview performs account and complete label-inventory reads, but zero API writes.
META_CLI_ENVIRONMENT=<environment_name> meta-cli labels create --name "Winner" --dry-run --json
# Omit --yes for an interactive confirmation showing the environment/account/name.
META_CLI_ENVIRONMENT=<environment_name> meta-cli labels create --name "Winner" --yes --json
```

`labels list` outputs label `id` and `name`; JSON retains the `data`/`paging` envelope and adds
`environment` and normalized `account_id`. Both commands read the account identity and refuse a
mismatch. They honor the existing process-only `META_CLI_ENVIRONMENT` override without modifying
persistent selection. Authorized account read access is required even for creation dry runs;
actual creation requires management permission (normally `ads_management`) and account access.
Meta account eligibility/API restrictions still apply; these flows are tested offline, not with
live permission probes.

Creation trims surrounding name whitespace and rejects blank names. It scans **all** account label
pages for an exact, case-sensitive match: one match returns its ID as `outcome: already_exists`
with `changed: false`; multiple matches fail without choosing an ID or writing. Use `labels list`
to inspect ambiguous IDs, then use an explicit ID for label application or choose a unique name.
No-op and dry-run paths do not prompt. A new-name dry run returns `outcome: would_create` and the
name-only `mutation`, with no fabricated ID. Only confirmed real creation POSTs `{"name": "..."}`
to the account's official SDK `/adlabels` edge; no status, budget, or delivery changes are made.
Creation requires a valid returned new label ID; a success-only acknowledgement without that ID
is insufficient. An accepted creation response is followed by a complete account-label readback to
verify the returned ID and name. JSON creation results include `environment`, `account_id`,
`dry_run`, `changed`, `outcome`, `mutation`, and the `label` when it exists (`verified: true` for a
readback-verified creation).
With `--yes --json`, output is machine-readable without a confirmation prompt.

Meta does not guarantee atomic name uniqueness: concurrent creators can race between preflight and
write. The CLI never retries writes automatically. An API failure, missing created ID, or failed
readback exits nonzero and may leave a created label in Meta; list labels before retrying. Known
credential values are redacted from SDK errors. Reusing or creating an account label alone does not
label any ad/campaign or activate delivery.

### Add an existing label to an ad or campaign

```bash
META_CLI_ENVIRONMENT=<environment_name> meta-cli ads add-label <ad_id> --label-id <label_id> --dry-run --json
META_CLI_ENVIRONMENT=<environment_name> meta-cli campaigns add-label <campaign_id> --label-id <label_id> --dry-run --json
# After reviewing the preview, authorize the same explicit target (omit --yes to confirm interactively):
META_CLI_ENVIRONMENT=<environment_name> meta-cli ads add-label <ad_id> --label-id <label_id> --yes --json
META_CLI_ENVIRONMENT=<environment_name> meta-cli campaigns add-label <campaign_id> --label-id <label_id> --yes --json
# Independent read-only verification:
META_CLI_ENVIRONMENT=<environment_name> meta-cli ads get <ad_id> --json
META_CLI_ENVIRONMENT=<environment_name> meta-cli campaigns get <campaign_id> --json
```

These commands accept one numeric target ID and one existing account label ID; they never create
labels implicitly. Preflight reads and validates the selected account, target identity/ownership,
and current label IDs, then fully enumerates account labels to prove the requested label exists in
that account (no page cap). A missing node `adlabels` field is **not** proof of an empty set.
Only when the field is absent, after validating target identity and account ownership, the CLI
explicitly GETs that ad's or campaign's `/adlabels` edge through the official SDK. It validates and
consumes **every page**, including empty intermediate pages, before accepting the complete label
set. A successfully completed empty edge confirms an unlabelled object; omitted data, malformed
pages/pagination, repeated cursors, duplicate IDs, or any page-fetch error do not. Unsafe initial
resolution fails before any write, including in dry runs.

An explicit node list (including `[]`) remains supported without a fallback request. Explicit null
or partial/malformed node fields still fail closed; they are never reinterpreted as absence.
The same rules apply to already-applied checks, repeated additions, and post-write readback. If
readback omits the node field, its edge must also resolve completely and contain every prior label
plus the requested label before `verified: true` can be returned. Unsafe readback reports possible
write success but failed verification, without retry or rollback. General `ads get` / `campaigns get`
output remains raw: omission there is still not proof of no labels. Missing objects or account
labels and account mismatches continue to fail closed.

`--dry-run` performs those reads but **zero API writes** and no prompt (`outcome: would_add`).
An already-applied label is a successful `already_applied` no-op without a prompt or write.
Otherwise confirmation shows environment, account, target, and label; `--yes`/`-y` bypasses it.
The official SDK `Ad.create_ad_label` / `Campaign.create_ad_label` POSTs only
`{"adlabels": [{"id": "<label_id>"}]}` to the selected object's **additive `/adlabels` edge**.
It does not replace the node's complete label field. Unrelated labels are retained server-side;
no status, budget, targeting, parent, or child objects are changed. Campaign labeling does not
label child ads. Account read access is required even for dry runs; actual labeling also requires
management permission and Meta account/API eligibility. This behavior is verified offline with
mocks and SDK request schemas, not live account permission probes.

The CLI checks raw mutation acknowledgements before the SDK can discard its `success` flag
(also for account-label creation and archiving). Explicit `success: false`, non-boolean success
values, Graph errors, malformed responses, and invalid/mismatched returned IDs fail closed, even
if the write may already have taken effect. A success-only `{"success": true}` acknowledgement
becomes an empty SDK object; additive labeling proceeds to mandatory readback rather than rejecting
that response. A raw empty dictionary is also allowed through **only for additive labeling**;
unknown nonempty responses without an accepted success flag or ID are rejected. Neither an empty
response nor an acknowledgement alone is verified success: the target identity/account/label
readback must verify that both the new label and every prior label remain. Label preflight and
readback require the identity actually returned by Meta, not an ID supplied by an SDK constructor.
Output includes `environment`, `account_id`, `object_id`,
`label`, `before_label_ids`, exact additive `mutation`, `dry_run`, `changed`, and `outcome`;
readback-verified writes also include `verified: true` and `after_label_ids` (`outcome: added`).
The additive endpoint avoids replacement lost-update races, but preflight and readback are not an
atomic transaction: another operator may concurrently add/remove labels or delete objects.
Concurrent additions are accepted; missing prior labels at readback fail verification. No-op state
is also only a point-in-time observation. Negative/malformed acknowledgements, mismatched response
IDs, API errors, or failed readback exit nonzero and may mean the label was applied: fetch the object
before retrying.
The CLI never retries or rolls back writes automatically and redacts known credentials from SDK
errors. Named-environment process routing does not change persistent selection.

### Archive one non-delivering ad (not delete)

```bash
META_CLI_ENVIRONMENT=<environment_name> meta-cli ads archive <ad_id> --dry-run --json
# After reviewing the preview; omit --yes to confirm interactively:
META_CLI_ENVIRONMENT=<environment_name> meta-cli ads archive <ad_id> --yes --json
META_CLI_ENVIRONMENT=<environment_name> meta-cli ads get <ad_id> --json
```

`ads archive` accepts one explicit numeric ad ID, not a campaign, ad set, selector, or bulk list.
It reads the configured account and selected ad, validating identity, account ownership, parent
IDs, `status`, `configured_status`, and `effective_status`. Both configured status fields must
agree. Supported configured states are `PAUSED` and `ACTIVE`, with one of these explicitly
non-delivering effective states: `PAUSED`, `ADSET_PAUSED`, `CAMPAIGN_PAUSED`, `DISAPPROVED`,
`PENDING_REVIEW`, `PENDING_BILLING_INFO`, `IN_PROCESS`, or `PREAPPROVED`. In particular, an ad
configured `ACTIVE` under a paused campaign or ad set can be archived **without activating it or
its parents**. Effectively `ACTIVE`, `WITH_ISSUES` (not proof of non-delivery), deleted, unknown,
missing, or inconsistent states fail closed. No activation/pause workaround is attempted.
Meta still decides which transitions the account/API permits; offline SDK support is not a live
eligibility guarantee. Account read access is needed even for dry runs; writes require authorized
management access (normally `ads_management`).

When all three status fields are already `ARCHIVED`, the command returns a successful
`outcome: already_archived` no-op, without a prompt or write. `--dry-run` performs read-only
preflight and returns `would_archive`, with zero API writes and no prompt. Otherwise confirmation
identifies the environment, account, ad, and current configured/effective states; `--yes`/`-y`
bypasses the prompt. The sole write is the official SDK `Ad.api_update` on the selected ad with
exactly `{"status": "ARCHIVED"}`. It never calls a delete endpoint, activates delivery, changes
labels/creative/budget/targeting, traverses children, or updates campaigns or ad sets. Archiving
is a status change, **not permanent deletion**; this command offers no unarchive operation.

Archive accepts a success-only acknowledgement or a matching returned ad ID, but rejects a raw
empty response and explicit negative/invalid acknowledgements before SDK parsing can hide them.
After an acknowledged write, the CLI fetches the ad again and requires the same identity,
account and parent IDs, with all status fields `ARCHIVED`. Verified success returns
`outcome: archived`, `changed: true`, and `verified: true`. Output includes `environment`,
`account_id`, `ad_id`, before/after status and parent snapshots, `dry_run`, and the exact `mutation`.
Dry-run/no-op results have `changed: false` and no fabricated after snapshot. Named-environment
process routing is reused without changing persistent selection.

Preflight and readback are point-in-time reads, not an atomic lock against other operators or
Meta's transient state changes. Failed writes, unknown acknowledgements, and failed readbacks
exit nonzero with guidance to fetch the ad before retrying: the archive may already have
succeeded. Eventual consistency can delay readback confirmation. The CLI never retries, rolls
back, or updates a parent to force a transition, and known credentials are redacted from SDK
errors. All development verification uses mocks/offline SDK schemas, not live mutations.

### Labels/archive outcomes and offline release checks

Successful mutation results have `ok: true` and the following `operation`/`outcome` values:

| `operation` | Read-only dry-run outcome | No-op outcome (including with `--dry-run`) | Verified write outcome |
| --- | --- | --- | --- |
| `account_label_create` | `would_create` | `already_exists` | `created` |
| `ad_add_label` / `campaign_add_label` | `would_add` | `already_applied` | `added` |
| `ad_archive` | `would_archive` | `already_archived` | `archived` |

Only verified writes return `changed: true` and `verified: true`. Dry runs and no-ops return
`changed: false` and omit `verified`; their `mutation` describes the intended payload, not a
write that occurred. JSON domain/API errors return `ok: false` and `error`, with exit status 1;
argument/parser errors and cancelled prompts may instead use normal CLI text. A post-write error
is not proof that Meta made no change. Inspect with `labels list`, `ads get`, or `campaigns get`
before deciding whether to retry; the CLI has no automatic retry or rollback.

No label rename/removal/deletion, bulk labeling, ad-set labeling, campaign archiving, or unarchive
command is provided by this interface. It does not automatically save reports: redirect `--json`
output to a chosen artifact path when needed. Verification is limited to the fields described
above, not a fresh inventory of all account objects or proof of live permissions.

The following **installed CLI help checks are credential-free**: no profile selection, account
reads, or Meta mutations are needed. Required IDs/options may be omitted with `--help`.

```bash
meta-cli --help
meta-cli labels --help
meta-cli labels list --help
meta-cli labels create --help
meta-cli ads add-label --help
meta-cli campaigns add-label --help
meta-cli ads archive --help
meta-cli ads get --help
meta-cli campaigns get --help
```

For a command-center installation, run the same checks through its actual wrapper from the
command-center root (do not override `META_CLI_BIN` to a development checkout):

```bash
./bin/meta-cli --help
./bin/meta-cli labels --help
./bin/meta-cli labels list --help
./bin/meta-cli labels create --help
./bin/meta-cli ads add-label --help
./bin/meta-cli campaigns add-label --help
./bin/meta-cli ads archive --help
./bin/meta-cli ads get --help
./bin/meta-cli campaigns get --help
```

A wrapper may require that its private store file exists, but help does not load credentials or
call Meta. Do not substitute `auth test`, real getters, or mutation dry runs for offline release
checks. Help confirms registration/options, not installed commit provenance or live API eligibility;
record the deployed commit/source separately. After installing development dependencies, verify
examples and safety behavior offline from the CLI source checkout:

```bash
env -u META_ACCESS_TOKEN -u META_APP_ID -u META_APP_SECRET \
  -u META_AD_ACCOUNT_ID -u META_CLI_ENVIRONMENT \
  LIVE_META_TESTS=0 META_CLI_ENVIRONMENTS_FILE="$(mktemp -d)/environments.yaml" \
  .venv/bin/python -m pytest \
  tests/test_labels_cli.py tests/test_object_labels_cli.py tests/test_ad_archive_cli.py \
  tests/test_verification_getters.py tests/test_labels_archive_workflow.py \
  tests/test_sdk_label_acknowledgements.py
```

These fixtures use synthetic profiles and mocked SDK calls; the README workflow and acknowledgement
regressions retain the official SDK request/parser path with network transport blocked. Re-run them
when upgrading the SDK: acknowledgement checks wrap each pending request's private response parser,
not SDK globals, and must remain compatible with its parsing behavior.

### Targeting discovery

```bash
meta-cli targeting search-interests --query "Tutoring" --json
meta-cli targeting search-categories --class family_statuses --query "parent" --json
meta-cli targeting search-categories --class user_device --query "iPhone" --json
meta-cli targeting search-locations --query "Gurugram" --country IN
meta-cli targeting search-locations --query "Noida" --country IN --json
```

Interest search returns Meta's interest IDs, names, audience-size bounds, and taxonomy paths.
Location search returns Meta's targeting key, name, type, country, and region. Use these discovery
commands so targeting updates rely on valid platform identifiers rather than guessed values.

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
meta-cli media video-status <video_id> --wait --json
```

`media upload-video` waits for Meta processing by default; use `--no-wait` to return immediately.
Use `media video-status <video_id>` to inspect an existing upload or add `--wait` to resume waiting
for processing after an interrupted upload command.

### Create flows

```bash
meta-cli campaigns create --config examples/campaign.yaml
meta-cli campaigns create --name "Traffic Campaign" --objective OUTCOME_TRAFFIC --dry-run --json
meta-cli campaigns update-budget <campaign_id> --daily-budget 1000 --dry-run --yes --json
meta-cli campaigns update-budget <campaign_id> --daily-budget 1000 --yes --json
meta-cli adsets create --config examples/adset.yaml
meta-cli adsets update-budget <adset_id> --daily-budget 5000 --yes
meta-cli adsets update-targeting <adset_id> --targeting-file examples/adset.yaml --yes
meta-cli adsets update-attribution <adset_id> \
  --attribution-spec-json '[{"event_type":"CLICK_THROUGH","window_days":7}]' \
  --dry-run --yes --json
meta-cli custom-conversions create \
  --name "Student chat initiated" \
  --event-source-id <pixel_id> \
  --rule-json '{"event":{"eq":"Student chat initiated"}}' \
  --custom-event-type CONTACT \
  --action-source-type WEBSITE \
  --dry-run --yes --json
meta-cli ads create --config examples/ad.yaml
meta-cli ads create --config examples/ad-placement-images.yaml --dry-run --json
meta-cli ads create --config examples/ad-placement-mixed-media.yaml --dry-run --json
meta-cli creatives create --config examples/ad.yaml --dry-run --json
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
optional, so existing non-dynamic ad-set behavior is unchanged. Ad-set creation also accepts an
`attribution_spec` JSON array in YAML or `--attribution-spec-json`; set it explicitly when cloning
an ad set so Meta's current default does not silently change the attribution window.

`campaigns update-budget` changes only `daily_budget`, supplied as a positive raw integer in minor
currency units. Before either a dry run or live update, it loads the selected account context and
fetches the campaign to validate its numeric ID, ownership, and current daily budget. Its structured
output identifies the operation, selected environment, account, target, current amount, and exact
mutation without exposing credentials. `--dry-run` performs those read-only validations but sends
no mutation. A live update requires confirmation unless `--yes` is supplied; fetch the campaign
again after it succeeds to verify the amount and delivery status.

`adsets update-budget` changes exactly one of `daily_budget` or `lifetime_budget` in minor currency
units. It requires confirmation unless `--yes` is supplied and supports `--dry-run`. Fetch the ad
set after every live budget update to verify the account, amount, and paused/active status.

`custom-conversions create` creates an account custom conversion from an exact JSON rule. Supply the
pixel/data-source ID, a Meta conversion category such as `CONTACT`, and optionally an action source
such as `WEBSITE`. The command requires confirmation unless `--yes` is supplied and supports a
credential-free `--dry-run`. Use `custom-conversions list` first to avoid duplicates, then fetch the
returned ID with `custom-conversions get` and verify availability and event timestamps before using
that ID as an ad set's `promoted_object.custom_conversion_id`.

For creative-only replacement workflows, `creatives create --config` builds and creates the same
creative payload that `ads create --config` would use, but it does not create a new ad. Use it with
`--dry-run --json` to inspect the creative payload, then attach the returned creative ID to an
existing ad with `ads update-creative`.

For Instagram delivery, set `instagram_user_id` in ad YAML or pass `--instagram-user-id`; use the
legacy `instagram_actor_id` / `--instagram-actor-id` only for accounts that still expose an actor
ID. If ad YAML or command flags omit `page_id` / `--page-id` and the Instagram identity, `ads create`
uses the selected named profile's optional `facebook_page_id` and `instagram_user_id`. Explicit ad
values take precedence, including an explicit legacy Instagram actor ID. Supplying `--auth-config`
is a deliberate legacy override and therefore does not borrow identity defaults from the selected
profile. If no explicit or profile Facebook Page ID is available, the existing validation error is
preserved. `creatives get` shows the identity field used by an existing working creative.

Set `url_tags` in ad YAML, or pass `--url-tags` to `ads create`, to add Meta URL-parameter templates
to the creative without changing its destination URL. Omit the leading `?`; one is stripped when
provided. This works for legacy and asset-feed creatives, including dynamic IDs such as
`campaign_id={{campaign.id}}&adset_id={{adset.id}}&ad_id={{ad.id}}`. Use `creatives get` to verify
the resulting `url_tags` before attaching a replacement creative to a live ad.

For placement-specific static or mixed image/video creative, `ads create` and `creatives create`
accept `image_assets`, `video_assets`, and `asset_customization_rules` in YAML. Each image asset has
a Meta image `hash`; each video asset has an uploaded Meta `video_id`; both use a unique, nonblank
`label`. Each rule has a Meta `customization_spec`, exactly one of `image_label` or `video_label`
referencing the corresponding asset, and an optional `priority`. The generated `asset_feed_spec`
adds labels as `adlabels`, emits Meta's `{\"name\": ...}` media-label shape, and uses
`AUTOMATIC_FORMAT` when both image and video assets are present. See
`examples/ad-placement-images.yaml` for dedicated static ratios and
`examples/ad-placement-mixed-media.yaml` for static feed/Stories assets plus a Reels video.

The equivalent CLI flags accept JSON arrays:

```bash
meta-cli ads create \
  --adset-id "$ADSET_ID" --name "Placement media" --page-id "$PAGE_ID" \
  --destination-url "https://example.com" --bodies "Find the right tutor" \
  --image-assets-json '[{"hash":"hash_4x5","label":"feed_4x5"},{"hash":"hash_1x1","label":"square_1x1"},{"hash":"hash_9x16","label":"stories_9x16"}]' \
  --video-assets-json '[{"video_id":"video_id_9x16","label":"reels_9x16"}]' \
  --asset-customization-rules-json '[{"customization_spec":{"publisher_platforms":["facebook","instagram"],"facebook_positions":["feed"],"instagram_positions":["stream"]},"image_label":"feed_4x5","priority":1},{"customization_spec":{"publisher_platforms":["facebook","instagram"],"facebook_positions":["facebook_reels"],"instagram_positions":["reels"]},"video_label":"reels_9x16","priority":2}]' \
  --dry-run --json
```

Placement assets require at least one customization rule, and customization rules cannot be used
without `image_assets` or `video_assets`. Asset labels must be unique across images and videos;
blank labels, rules with both/neither label type, and rules that reference unknown or wrong media
labels are rejected. Meta API v22+ no longer supports segment asset customization for multiple text
variants, so placement rules accept at most one headline, body, and description. For multiple copy
variants plus several uploaded image ratios, use `image_hashes` without
`asset_customization_rules`; Meta then optimizes the asset-feed combinations. `image_hashes` and
`image_assets` are mutually exclusive. Legacy `video_id` remains the single-video flow and cannot
be mixed with images; use labeled `video_assets` for mixed placement media. Existing
`image_hashes` behavior is unchanged, including the single-image story payload and multi-image
asset-feed payload.

`adsets update-targeting` replaces the complete targeting object, so first export or retain the
existing targeting and include every constraint and placement that must remain. Supply exactly one
of `--targeting-json` or `--targeting-file`; a JSON/YAML file may contain the targeting object
itself or an ad set config with a top-level `targeting` key. The command requires confirmation
unless `--yes` is passed and supports `--dry-run`.

`adsets update-attribution` replaces the complete attribution-spec array. Fetch the ad set first,
retain every attribution entry that should remain, and dry-run the exact replacement. The command
requires confirmation unless `--yes` is passed.

### Status control

```bash
meta-cli campaigns pause <campaign_id>
meta-cli campaigns resume <campaign_id>
meta-cli campaigns delete <campaign_id> --dry-run --json
meta-cli campaigns delete <campaign_id> --yes --json
meta-cli adsets pause <adset_id>
meta-cli adsets resume <adset_id>
meta-cli ads pause <ad_id>
meta-cli ads resume <ad_id>
```

`campaigns delete` is deliberately limited to campaigns whose configured status is `PAUSED`.
The command fetches and validates the current campaign before acting, requires confirmation unless
`--yes` is passed, and supports a read-only `--dry-run` that emits the campaign and proposed action.
Deletion cannot be undone and also removes the campaign's child objects from normal management
views. Meta retains historical delivery data for reporting, but export any evidence you need before
deletion because the campaign cannot be restored.

---

## YAML examples

- `examples/campaign.yaml`
- `examples/adset.yaml`
- `examples/ad.yaml`
- `examples/ad-placement-images.yaml`
- `examples/ad-placement-mixed-media.yaml`

Use returned media IDs in ad config:

- image upload → `image_hashes`, or `image_assets[].hash` for placement-specific images
- video upload → `video_id` for one video, or `video_assets[].video_id` for placement-specific mixed media

---

## Safety notes

- New campaigns, ad sets, and ads default to `PAUSED`
- Use `--dry-run` before real create/update/delete operations
- Pause/resume, ad-set attribution replacement, custom-conversion creation, and campaign deletion require confirmation unless `--yes` is passed
- Campaign deletion refuses non-paused campaigns and cannot be undone
- Account-label creation, additive labeling, and single-ad archiving confirm actual writes unless `--yes` is passed; their dry runs make read-only API requests, not offline checks
- Additive labeling retains unrelated labels; archiving refuses delivering/unknown states and updates only the selected ad's status, not its parents
- Label/archive writes report success only after readback; a failure after writing may still mean Meta changed, so inspect before retrying
- Check the intended environment before account work and immediately before a live mutation
- Validate auth (`meta-cli auth test`) before live operations; use only `--help` and mocked tests for credential-free release verification

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

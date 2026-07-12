# Meta setup and configuration

This guide covers first-time Meta setup, secure named environments, and migration from legacy auth
files.

## Meta setup (first-time users)

### 1) Confirm business and ad account access

In `business.facebook.com`:

1. Open **Business Settings**.
2. Confirm the business owns, or has partner access to, the target ad account.
3. Confirm the user or system user has the required ad account permissions.

### 2) Create a Meta app and enable Marketing API

In `developers.facebook.com`:

1. Create an app (Business type recommended).
2. Add the **Marketing API** product.
3. Record the app ID and app secret securely.

### 3) Generate an access token

A system-user token from Business Settings is recommended. Typical required scopes are:

- `ads_read`
- `ads_management`

Treat the access token and app secret as secrets. Do not put them in shell history, source control,
logs, screenshots, or support messages.

### 4) Find the ad account ID

The CLI accepts either the numeric ID or `act_<id>`. Numeric values are normalized to the `act_...`
form.

## Recommended configuration: named environments

Named environments make the account and credential context explicit and persistent. The CLI resolves
the environment store in this order:

1. `$META_CLI_ENVIRONMENTS_FILE`, if set.
2. `$XDG_CONFIG_HOME/meta-ads-cli/environments.yaml`, if `XDG_CONFIG_HOME` is set.
3. `~/.config/meta-ads-cli/environments.yaml`.

`META_CLI_ENVIRONMENTS_FILE` is recommended for CI, tests, and other automation so they cannot read
or modify a real home-directory store. It changes the file location only; it does not select a
profile.

### Create the store securely

Create the default store with placeholders, replace them locally, and enforce owner-only access:

```bash
mkdir -p "$HOME/.config/meta-ads-cli"
cat > "$HOME/.config/meta-ads-cli/environments.yaml" <<'YAML'
active_profile: null
profiles:
  sandbox:
    display_name: Sandbox account
    access_token: "replace-with-access-token"
    app_id: "replace-with-app-id"
    app_secret: "replace-with-app-secret"
    ad_account_id: "act_1234567890"
    api_version: "v25.0"
    # Optional metadata and ads-create identity defaults:
    # system_user_id: "1234567890"
    # facebook_page_id: "1234567890"
    # instagram_user_id: "1234567890"
YAML
chmod 600 "$HOME/.config/meta-ads-cli/environments.yaml"
```

For an isolated temporary or automation location, set the override before creating the file:

```bash
export META_CLI_ENVIRONMENTS_FILE="$(mktemp -d)/environments.yaml"
mkdir -p "$(dirname "$META_CLI_ENVIRONMENTS_FILE")"
# Write the same YAML schema to "$META_CLI_ENVIRONMENTS_FILE", then:
chmod 600 "$META_CLI_ENVIRONMENTS_FILE"
```

The complete schema is:

- `active_profile`: selected profile name or `null`; do not set it during initial setup.
- `profiles`: mapping of profile names to profile records.
  - `access_token`: required secret string.
  - `app_id`: required string.
  - `app_secret`: required secret string.
  - `ad_account_id`: required numeric or `act_...` account ID.
  - `api_version`: optional; defaults to `v25.0`.
  - `display_name`: optional human-readable label.
  - `system_user_id`: optional metadata.
  - `facebook_page_id`: optional `ads create` default.
  - `instagram_user_id`: optional `ads create` default.

Unknown keys, blank required values, malformed account IDs, blank profile names, and profile names with
surrounding whitespace are rejected. Lowercase keys are required in this named-store format.

The file contains credentials. Keep it out of source control and backups or artifacts with broad
access, and never print or log its contents. Manually created files must be protected with `0600` as
shown above. When `meta-cli` persists a selection, it writes atomically where supported and enforces
`0600` on the resulting file.

### Inspect, select, and validate

A new store has no active profile. **The CLI never automatically selects the first or only profile.**
Use the environment commands explicitly:

```bash
meta-cli environments list
meta-cli environments current
meta-cli environments use sandbox
meta-cli environments current
meta-cli auth test
```

Before selection, `current` exits nonzero and explains how to select a profile. `use` accepts only a
name already in `profiles` and persists it for later invocations. `list` marks the active profile.
Add `--json` to `list`, `current`, or `use` for structured output.

Environment command output contains only non-secret identity metadata: profile name, active status,
display name, ad account ID, API version, and optional system-user/Page/Instagram IDs. It never
contains an access token or app secret.

Standard commands use the selected environment and fail with setup guidance when no profile is
selected or the selected profile no longer exists. A successful `meta-cli auth test` reports
`Active environment: <name>`. Its JSON output includes:

```json
{
  "ok": true,
  "auth_source": "named_environment",
  "active_environment": "sandbox",
  "account": {}
}
```

The `account` object is populated from Meta; it is abbreviated above.

### Page and Instagram identity defaults

A selected profile's optional `facebook_page_id` and `instagram_user_id` are defaults for
`ads create` only when the corresponding command flags or ad YAML values are omitted. Explicit ad
flags and YAML values take precedence. An explicit legacy `instagram_actor_id` also prevents the
profile Instagram user ID from being injected. Existing creative-ID flows do not require these
values.

If no Facebook Page ID is available explicitly or from the selected profile, existing ad validation
still fails. Named environments do not change spend safety: campaigns, ad sets, and ads default to
`PAUSED`; use `--dry-run` before creating or updating; and pause/resume or spend-affecting updates
retain confirmation prompts unless `--yes` is passed.

## Legacy auth files and migration

Explicit flat auth YAML files remain supported for migration, existing scripts, and deliberate
one-off overrides. Their format uses uppercase keys:

```yaml
META_ACCESS_TOKEN: "replace-with-access-token"
META_APP_ID: "replace-with-app-id"
META_APP_SECRET: "replace-with-app-secret"
META_AD_ACCOUNT_ID: "act_1234567890"
META_API_VERSION: "v25.0"
```

Protect legacy files with `0600` too. Pass one explicitly using `--config` for `auth test`, or
`--auth-config` for other commands:

```bash
meta-cli auth test --config "$HOME/.meta-ads-auth.yaml"
meta-cli campaigns list --auth-config "$HOME/.meta-ads-auth.yaml"
meta-cli ads create --config examples/ad.yaml --auth-config "$HOME/.meta-ads-auth.yaml"
```

### Configuration precedence

1. If `--config`/`--auth-config` is supplied, that explicit legacy file is used instead of the
   selected named environment.
2. Matching ambient `META_*` credential variables override keys from that explicit legacy file.
3. Without an explicit legacy file, ambient credential variables are not a credential source; the
   explicitly selected named environment is used.

Because an explicit legacy file bypasses the named environment, it does not borrow that profile's
Facebook Page or Instagram defaults. Supply those in the ad config or flags. `auth test` reports
`Active environment: none (explicit legacy config override)`; JSON reports
`"auth_source": "legacy_config"` and `"active_environment": null`.

### Migration steps

1. Create the named store with `active_profile: null`.
2. For each legacy auth file, add a profile and translate its uppercase keys to the lowercase named
   profile keys documented above.
3. Optionally add `display_name`, `system_user_id`, `facebook_page_id`, and `instagram_user_id`.
4. Run `meta-cli environments list`; this inspects identity metadata without revealing secrets.
5. Run `meta-cli environments use <name>` explicitly.
6. Run `meta-cli environments current`, then `meta-cli auth test`.
7. Retain the legacy file for explicit overrides if needed, or remove it according to your
   credential rotation and secret-retention policy.

Do not pre-populate `active_profile` as part of initial setup. Explicit selection is an intentional
safety boundary between accounts.

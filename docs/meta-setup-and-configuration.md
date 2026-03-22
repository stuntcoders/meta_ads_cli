# Meta setup and configuration

This guide contains the full first-time Meta setup and CLI configuration steps.

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

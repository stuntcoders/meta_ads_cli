"""Single-ad archiving: validate non-delivery, update only status, then read back."""
from __future__ import annotations

from meta_cli.cli_utils import require_confirmation
from meta_cli.commands.labels import _normalize_account_id
from meta_cli.commands.object_labels import _numeric_id
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.sdk import MetaSDKClient

ARCHIVE_FIELDS = [
    "id", "account_id", "name", "status", "configured_status", "effective_status",
    "adset_id", "campaign_id",
]
# WITH_ISSUES does not establish non-delivery. Unknown future states fail closed.
NON_DELIVERING_EFFECTIVE_STATUSES = frozenset({
    "PAUSED", "ADSET_PAUSED", "CAMPAIGN_PAUSED", "DISAPPROVED", "PENDING_REVIEW",
    "PENDING_BILLING_INFO", "IN_PROCESS", "PREAPPROVED",
})


def _read_ad(client: MetaSDKClient, ad_id: str, account_id: str) -> dict:
    ad = client.get_ad_details(ad_id, fields=ARCHIVE_FIELDS)
    if not isinstance(ad, dict) or _numeric_id(ad.get("id"), "Ad ID") != ad_id:
        raise ConfigError("Ad lookup did not match the requested ID")
    if _normalize_account_id(ad.get("account_id")) != account_id:
        raise ConfigError("Ad does not belong to the configured account")
    state = {"id": ad_id, "account_id": account_id}
    for field in ("adset_id", "campaign_id"):
        state[field] = _numeric_id(ad.get(field), f"Ad {field}")
    for field in ("status", "configured_status", "effective_status"):
        value = ad.get(field)
        if not isinstance(value, str) or not value:
            raise ConfigError(f"Ad {field} is missing or invalid; cannot safely archive")
        state[field] = value
    if state["status"] != state["configured_status"]:
        raise ConfigError("Ad status and configured_status disagree; fetch again before archiving")
    return state


def _already_archived(state: dict) -> bool:
    return all(state[field] == "ARCHIVED"
               for field in ("status", "configured_status", "effective_status"))


def archive_ad(client: MetaSDKClient, ad_id: str, *, dry_run: bool, yes: bool) -> dict:
    ad_id = _numeric_id(ad_id, "Ad ID")
    account_id = _normalize_account_id(client.credentials.ad_account_id)
    account = client.get_account_details(fields=["id"])
    if (not isinstance(account, dict)
            or _normalize_account_id(account.get("id")) != account_id):
        raise ConfigError("Account lookup did not match the configured account")
    before = _read_ad(client, ad_id, account_id)
    operation = {
        "ok": True, "operation": "ad_archive", "environment": client.active_environment,
        "account_id": account_id, "ad_id": ad_id, "before": before,
        "mutation": {"status": "ARCHIVED"}, "dry_run": dry_run, "changed": False,
    }
    if _already_archived(before):
        return {**operation, "outcome": "already_archived"}
    if (before["configured_status"] not in {"ACTIVE", "PAUSED"}
            or before["effective_status"] not in NON_DELIVERING_EFFECTIVE_STATUSES):
        raise ConfigError(
            "Unsupported ad state for safe archiving: requires configured ACTIVE/PAUSED and "
            "a recognized non-delivering effective status, or fully ARCHIVED for a no-op. "
            "Deleted, delivering, inconsistent, and unknown states are refused; no write performed."
        )
    if dry_run:
        return {**operation, "outcome": "would_archive"}
    require_confirmation(
        f"Archive only ad {ad_id} in {client.active_environment or 'explicit auth'} / {account_id} "
        f"({before['configured_status']} / {before['effective_status']}; no deletion or parent changes)?",
        yes=yes,
    )
    try:
        result = client.update_ad_status(ad_id, "ARCHIVED")
        if (not isinstance(result, dict) or result.get("success") is False
                or ("id" in result and str(result["id"]) != ad_id)
                or not (result.get("success") is True or str(result.get("id")) == ad_id)):
            raise APIError("Meta did not acknowledge the archive update")
    except (APIError, ValueError) as exc:
        raise APIError(
            f"Archive write for ad {ad_id} is unconfirmed: {exc}. It may have succeeded; "
            "fetch the ad before retrying. No retry or rollback was attempted."
        ) from exc
    try:
        after = _read_ad(client, ad_id, account_id)
        if not _already_archived(after):
            raise APIError("Readback did not confirm ARCHIVED configured and effective status")
        if any(after[field] != before[field] for field in ("adset_id", "campaign_id")):
            raise APIError("Readback returned different ad parent IDs")
    except (APIError, ConfigError, ValueError) as exc:
        raise APIError(
            f"Archive write for ad {ad_id} may have succeeded, but verification failed: {exc}. "
            "Fetch the ad before retrying; no rollback was attempted."
        ) from exc
    return {**operation, "outcome": "archived", "changed": True, "verified": True, "after": after}

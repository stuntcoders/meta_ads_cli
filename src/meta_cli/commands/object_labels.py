"""Shared preflight and readback for additive ad/campaign labels."""
from __future__ import annotations

from meta_cli.cli_utils import require_confirmation
from meta_cli.commands.labels import _account_labels, _normalize_account_id, _validate_account
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.sdk import MetaSDKClient

OBJECT_LABEL_FIELDS = ["id", "account_id", "name", "adlabels"]


def _numeric_id(value: object, description: str) -> str:
    text = str(value or "")
    if not text.isascii() or not text.isdigit():
        raise ConfigError(f"{description} must be a numeric ID")
    return text


def _read_target(client: MetaSDKClient, object_type: str, object_id: str, account_id: str):
    target = client.get_object_label_details(object_type, object_id, fields=OBJECT_LABEL_FIELDS)
    if not isinstance(target, dict) or _numeric_id(target.get("id"), "Target ID") != object_id:
        raise ConfigError("Target lookup did not match the requested ID")
    if _normalize_account_id(target.get("account_id")) != account_id:
        raise ConfigError("Target does not belong to the configured account")
    # Missing/null is not evidence of an empty set. Refuse partial/unknown shapes.
    labels = target.get("adlabels")
    if not isinstance(labels, list):
        raise APIError("Target adlabels must be an explicit list; missing/partial labels are unsafe")
    ids = []
    for label in labels:
        if not isinstance(label, dict):
            raise APIError("Target adlabels contains an invalid label")
        ids.append(_numeric_id(label.get("id"), "Current label ID"))
    if len(ids) != len(set(ids)):
        raise APIError("Target adlabels contains duplicate IDs; retry the read")
    return ids


def apply_object_label(
    client: MetaSDKClient, object_type: str, object_id: str, label_id: str,
    *, dry_run: bool, yes: bool,
) -> dict:
    if object_type not in {"ad", "campaign"}:
        raise ConfigError("Only ads and campaigns support this label operation")
    object_id = _numeric_id(object_id, "Target ID")
    label_id = _numeric_id(label_id, "Label ID")
    account_id = _validate_account(client)
    before = _read_target(client, object_type, object_id, account_id)
    # Full account enumeration proves both existence and ownership without relying
    # on the differently shaped AdLabel.account field or a capped inventory.
    matches = [label for label in _account_labels(client) if label["id"] == label_id]
    if len(matches) != 1:
        raise ConfigError("Label ID was not found in the configured account; no write performed")
    operation = {
        "ok": True, "operation": f"{object_type}_add_label",
        "environment": client.active_environment, "account_id": account_id,
        "object_id": object_id, "label": matches[0], "before_label_ids": before,
        "dry_run": dry_run, "changed": False,
        "mutation": {"adlabels": [{"id": label_id}]},
    }
    if label_id in before:
        return {**operation, "outcome": "already_applied"}
    if dry_run:
        return {**operation, "outcome": "would_add"}
    require_confirmation(
        f"Add label {label_id} to {object_type} {object_id} in "
        f"{client.active_environment or 'explicit auth'} / {account_id} (retain other labels)?",
        yes=yes,
    )
    client.add_object_label(object_type, object_id, label_id)
    try:
        after = _read_target(client, object_type, object_id, account_id)
        if not set(before + [label_id]).issubset(after):
            raise APIError("Readback did not retain all prior labels and the requested label")
    except (APIError, ConfigError, ValueError) as exc:
        raise APIError(
            f"Label write for {object_type} {object_id} may have succeeded, but verification "
            f"failed: {exc}. Fetch the object before retrying; no rollback was attempted."
        ) from exc
    return {
        **operation, "outcome": "added", "changed": True,
        "verified": True, "after_label_ids": after,
    }

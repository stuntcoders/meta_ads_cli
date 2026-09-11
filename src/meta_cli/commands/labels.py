from __future__ import annotations

from typing import Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error, require_confirmation
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table
from meta_cli.sdk import MetaSDKClient

app = typer.Typer(help="Account adlabel operations (not creative asset labels)")
LABEL_FIELDS = ["id", "name"]


def _normalize_account_id(value: object) -> str:
    account_id = str(value or "").strip()
    if account_id.startswith("act_"):
        account_id = account_id[4:]
    if not account_id.isascii() or not account_id.isdigit():
        raise ConfigError("Account ID is missing or invalid")
    return f"act_{account_id}"


def _validate_account(client: MetaSDKClient) -> str:
    account_id = _normalize_account_id(client.credentials.ad_account_id)
    account = client.get_account_details(fields=["id"])
    if _normalize_account_id(account.get("id")) != account_id:
        raise ConfigError("Account lookup did not match the configured account")
    return account_id


def _account_labels(client: MetaSDKClient) -> list[dict[str, str]]:
    # Safety checks must never use a capped or resumed inventory.
    rows = client.list_ad_labels(
        fields=LABEL_FIELDS, auto_paginate=True, max_pages=None, include_paging=False
    )
    if not isinstance(rows, list):
        raise APIError("Account label lookup returned an invalid inventory")
    labels = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise APIError("Account label lookup returned an invalid label")
        label_id = str(row.get("id") or "")
        name = row.get("name")
        if not label_id.isascii() or not label_id.isdigit() or not isinstance(name, str):
            raise APIError("Account label lookup returned an invalid label ID or name")
        if label_id in seen:
            raise APIError("Account label lookup returned duplicate IDs; retry the read")
        seen.add(label_id)
        labels.append({"id": label_id, "name": name})
    return labels


@app.command("list")
def list_labels(
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    limit: int = typer.Option(50, min=1, max=500, help="Maximum rows per request page"),
    after: Optional[str] = typer.Option(None, "--after", help="Cursor to fetch next page from"),
    before: Optional[str] = typer.Option(None, "--before", help="Cursor to fetch previous page from"),
    paginate: bool = typer.Option(True, "--paginate/--no-paginate", help="Auto-follow pagination"),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", min=1, help="Maximum pages to fetch"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        if after and before:
            raise ConfigError("Use either --after or --before, not both")
        client = build_client(auth_config)
        account_id = _validate_account(client)
        result = client.list_ad_labels(
            fields=LABEL_FIELDS,
            limit=limit,
            after=after,
            before=before,
            auto_paginate=paginate,
            max_pages=max_pages,
            include_paging=json_output,
        )
        if json_output:
            emit(
                {**result, "environment": client.active_environment, "account_id": account_id},
                as_json=True,
            )
            return
        print_table(
            f"Labels — {client.active_environment or 'explicit auth'} / {account_id}",
            ["ID", "Name"],
            [[item.get("id"), item.get("name")] for item in result],
            False,
        )
    except (ConfigError, APIError, ValueError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("create")
def create_label(
    name: str = typer.Option(..., "--name", help="Label name (trimmed; exact, case-sensitive reuse)"),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Read account/labels and preview; no writes"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        name = name.strip()
        if not name:
            raise ConfigError("Label name must not be blank")
        client = build_client(auth_config)
        account_id = _validate_account(client)
        labels = _account_labels(client)
        matches = [label for label in labels if label["name"] == name]
        if len(matches) > 1:
            raise ConfigError(
                "Multiple account labels have this exact name; no label was selected or created. "
                "List labels and use an explicit label ID for application, or choose a unique name."
            )
        operation = {
            "ok": True,
            "operation": "account_label_create",
            "environment": client.active_environment,
            "account_id": account_id,
            "dry_run": dry_run,
            "changed": False,
            "mutation": {"name": name},
        }
        if matches:
            emit(
                {**operation, "outcome": "already_exists", "label": matches[0]},
                as_json=json_output,
            )
            return
        if dry_run:
            emit({**operation, "outcome": "would_create"}, as_json=json_output)
            return
        require_confirmation(
            f"Create account label {name!r} in "
            f"{client.active_environment or 'explicit auth'} / {account_id}?",
            yes=yes,
        )
        result = client.create_ad_label(name)
        label_id = result["id"]
        try:
            verified = [label for label in _account_labels(client) if label["id"] == label_id]
            if len(verified) != 1 or verified[0]["name"] != name:
                raise APIError("Created label ID/name was not found in the account readback")
        except APIError as exc:
            raise APIError(
                f"Meta returned created label ID {label_id}, but verification failed: {exc}. "
                "The label may already exist; list account labels before retrying."
            ) from exc
        emit(
            {
                **operation,
                "changed": True,
                "outcome": "created",
                "verified": True,
                "label": verified[0],
            },
            as_json=json_output,
        )
    except (ConfigError, APIError, ValueError) as exc:
        handle_cli_error(exc, as_json=json_output)

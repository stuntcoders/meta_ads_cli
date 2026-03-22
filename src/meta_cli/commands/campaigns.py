from __future__ import annotations

from typing import Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error, require_confirmation
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table

app = typer.Typer(help="Campaign operations")

CAMPAIGN_FIELDS = [
    "id",
    "name",
    "status",
    "objective",
    "daily_budget",
    "lifetime_budget",
]


@app.command("list")
def list_campaigns(
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    limit: int = typer.Option(50, min=1, max=500, help="Maximum rows per request page"),
    after: Optional[str] = typer.Option(None, "--after", help="Cursor to fetch next page from"),
    before: Optional[str] = typer.Option(None, "--before", help="Cursor to fetch previous page from"),
    paginate: bool = typer.Option(True, "--paginate/--no-paginate", help="Auto-follow pagination"),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", min=1, help="Maximum pages to fetch"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        campaigns = client.list_campaigns(
            fields=CAMPAIGN_FIELDS,
            limit=limit,
            after=after,
            before=before,
            auto_paginate=paginate,
            max_pages=max_pages,
        )
        rows = [
            [
                item.get("id"),
                item.get("name"),
                item.get("status"),
                item.get("objective"),
                item.get("daily_budget"),
                item.get("lifetime_budget"),
            ]
            for item in campaigns
        ]
        print_table("Campaigns", ["ID", "Name", "Status", "Objective", "Daily", "Lifetime"], rows, json_output, campaigns)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("pause")
def pause_campaign(
    campaign_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show action without updating"),
) -> None:
    _change_status(campaign_id, "PAUSED", auth_config, yes, json_output, dry_run)


@app.command("resume")
def resume_campaign(
    campaign_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show action without updating"),
) -> None:
    _change_status(campaign_id, "ACTIVE", auth_config, yes, json_output, dry_run)


def _change_status(
    campaign_id: str,
    status: str,
    auth_config: Optional[str],
    yes: bool,
    json_output: bool,
    dry_run: bool,
) -> None:
    try:
        require_confirmation(
            f"Are you sure you want to set campaign {campaign_id} to {status}?", yes=yes
        )
        if dry_run:
            emit({"ok": True, "dry_run": True, "campaign_id": campaign_id, "status": status}, as_json=json_output)
            return
        client = build_client(auth_config)
        result = client.update_campaign_status(campaign_id, status)
        emit(
            {"ok": True, "campaign_id": campaign_id, "status": status, "result": result},
            as_json=json_output,
        )
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)

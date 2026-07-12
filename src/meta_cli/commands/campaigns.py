from __future__ import annotations

from typing import List, Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error, require_confirmation
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table
from meta_cli.schemas import CampaignCreateConfig, load_yaml_model

app = typer.Typer(help="Campaign operations")

CAMPAIGN_FIELDS = [
    "id",
    "name",
    "status",
    "objective",
    "daily_budget",
    "lifetime_budget",
]

CAMPAIGN_DETAIL_FIELDS = [
    "id",
    "name",
    "status",
    "objective",
    "buying_type",
    "daily_budget",
    "lifetime_budget",
    "start_time",
    "stop_time",
    "created_time",
    "updated_time",
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
        result = client.list_campaigns(
            fields=CAMPAIGN_FIELDS,
            limit=limit,
            after=after,
            before=before,
            auto_paginate=paginate,
            max_pages=max_pages,
            include_paging=json_output,
        )
        if json_output:
            emit(result, as_json=True)
            return

        campaigns = result
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


@app.command("get")
def get_campaign(
    campaign_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        campaign = client.get_campaign_details(campaign_id, fields=CAMPAIGN_DETAIL_FIELDS)
        if json_output:
            emit(campaign, as_json=True)
            return

        rows = [[key, campaign.get(key)] for key in CAMPAIGN_DETAIL_FIELDS]
        print_table(f"Campaign {campaign_id}", ["Field", "Value"], rows, False)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("create")
def create_campaign(
    config: Optional[str] = typer.Option(None, "--config", help="Path to campaign YAML config"),
    name: Optional[str] = typer.Option(None, "--name", help="Campaign name"),
    objective: Optional[str] = typer.Option(None, "--objective", help="Campaign objective"),
    buying_type: str = typer.Option("AUCTION", "--buying-type", help="Campaign buying type"),
    special_ad_categories: Optional[str] = typer.Option(
        None,
        "--special-ad-categories",
        help="Comma-separated special ad categories",
    ),
    daily_budget: Optional[int] = typer.Option(
        None, "--daily-budget", help="Daily budget in minor units"
    ),
    lifetime_budget: Optional[int] = typer.Option(
        None, "--lifetime-budget", help="Lifetime budget in minor units"
    ),
    is_adset_budget_sharing_enabled: Optional[bool] = typer.Option(
        None,
        "--adset-budget-sharing/--no-adset-budget-sharing",
        help="Allow ad sets to share part of their budgets when using ad set budgets",
    ),
    status: str = typer.Option("PAUSED", "--status", help="Campaign status"),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and print payload only"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        campaign_config = _build_campaign_config(
            config_path=config,
            name=name,
            objective=objective,
            buying_type=buying_type,
            special_ad_categories=special_ad_categories,
            daily_budget=daily_budget,
            lifetime_budget=lifetime_budget,
            is_adset_budget_sharing_enabled=is_adset_budget_sharing_enabled,
            status=status,
        )
        payload = campaign_config.to_payload()
        if dry_run:
            emit({"ok": True, "dry_run": True, "payload": payload}, as_json=json_output)
            return

        client = build_client(auth_config)
        result = client.create_campaign(payload)
        emit({"ok": True, "campaign": result, "payload": payload}, as_json=json_output)
    except (ConfigError, APIError, ValueError) as exc:
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


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _build_campaign_config(
    config_path: Optional[str],
    name: Optional[str],
    objective: Optional[str],
    buying_type: str,
    special_ad_categories: Optional[str],
    daily_budget: Optional[int],
    lifetime_budget: Optional[int],
    is_adset_budget_sharing_enabled: Optional[bool],
    status: str,
) -> CampaignCreateConfig:
    if config_path:
        return load_yaml_model(config_path, CampaignCreateConfig)

    return CampaignCreateConfig(
        name=name,
        objective=objective,
        buying_type=buying_type,
        special_ad_categories=_split_csv(special_ad_categories),
        daily_budget=daily_budget,
        lifetime_budget=lifetime_budget,
        is_adset_budget_sharing_enabled=is_adset_budget_sharing_enabled,
        status=status,
    )


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

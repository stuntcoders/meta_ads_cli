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

CAMPAIGN_DELETE_FIELDS = [
    "id",
    "name",
    "status",
    "configured_status",
    "effective_status",
]

CAMPAIGN_BUDGET_FIELDS = [
    "id",
    "account_id",
    "name",
    "status",
    "configured_status",
    "effective_status",
    "daily_budget",
    "lifetime_budget",
]

CAMPAIGN_DETAIL_FIELDS = [
    "id",
    "name",
    "status",
    "configured_status",
    "effective_status",
    "objective",
    "buying_type",
    "daily_budget",
    "lifetime_budget",
    "budget_remaining",
    "is_adset_budget_sharing_enabled",
    "issues_info",
    "recommendations",
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
    bid_strategy: Optional[str] = typer.Option(
        None,
        "--bid-strategy",
        help="Campaign bid strategy (e.g. LOWEST_COST_WITHOUT_CAP for CBO campaigns)",
    ),
    bid_amount: Optional[int] = typer.Option(
        None, "--bid-amount", help="Campaign bid amount in minor units (for capped strategies)"
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
            bid_strategy=bid_strategy,
            bid_amount=bid_amount,
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


@app.command("update-budget")
def update_campaign_budget(
    campaign_id: str,
    daily_budget: int = typer.Option(
        ..., "--daily-budget", help="New raw daily budget in minor currency units"
    ),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate account ownership and print the exact mutation without updating",
    ),
) -> None:
    """Safely update only a campaign's raw daily budget."""
    try:
        validated_campaign_id = _validate_campaign_id(campaign_id)
        if daily_budget < 1:
            raise ValueError("--daily-budget must be a positive integer in minor currency units")

        client = build_client(auth_config)
        configured_account_id = _configured_account_id(client)
        campaign = client.get_campaign_details(
            validated_campaign_id,
            fields=CAMPAIGN_BUDGET_FIELDS,
        )
        target = _validate_campaign_budget_target(
            campaign,
            campaign_id=validated_campaign_id,
            configured_account_id=configured_account_id,
        )
        mutation = {"daily_budget": daily_budget}
        operation = {
            "ok": True,
            "dry_run": dry_run,
            "operation": "campaign_daily_budget_update",
            "environment": getattr(client, "active_environment", None),
            "account_id": configured_account_id,
            "target": target,
            "mutation": mutation,
        }

        require_confirmation(
            f"Update campaign {validated_campaign_id} in {configured_account_id} "
            f"from raw daily budget {target['current_daily_budget']} to {daily_budget}?",
            yes=yes,
        )
        if dry_run:
            emit(operation, as_json=json_output)
            return

        result = client.update_campaign_budget(validated_campaign_id, daily_budget)
        emit({**operation, "result": result}, as_json=json_output)
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


@app.command("delete")
def delete_campaign(
    campaign_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without deleting"),
) -> None:
    """Permanently delete a paused campaign."""
    try:
        client = build_client(auth_config)
        campaign = client.get_campaign_details(campaign_id, fields=CAMPAIGN_DELETE_FIELDS)
        configured_status = campaign.get("configured_status") or campaign.get("status")
        if configured_status != "PAUSED":
            raise ConfigError(
                f"Refusing to delete campaign {campaign_id}: configured status is "
                f"{configured_status or 'unknown'}, not PAUSED. Pause it first."
            )

        if dry_run:
            emit(
                {
                    "ok": True,
                    "dry_run": True,
                    "action": "delete",
                    "campaign_id": campaign_id,
                    "campaign": campaign,
                    "irreversible": True,
                },
                as_json=json_output,
            )
            return

        campaign_name = campaign.get("name") or campaign_id
        require_confirmation(
            f"Permanently delete paused campaign '{campaign_name}' ({campaign_id})? "
            "This cannot be undone.",
            yes=yes,
        )
        result = client.delete_campaign(campaign_id)
        emit(
            {
                "ok": True,
                "deleted": True,
                "campaign_id": campaign_id,
                "previous_campaign": campaign,
                "result": result,
            },
            as_json=json_output,
        )
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


def _validate_campaign_id(campaign_id: str) -> str:
    value = campaign_id.strip()
    if not value or not value.isdigit():
        raise ValueError("Campaign ID must contain digits only")
    return value


def _normalize_account_id(account_id: object, *, source: str) -> str:
    value = str(account_id or "").strip()
    if value.startswith("act_"):
        value = value[4:]
    if not value or not value.isdigit():
        raise ConfigError(f"{source} account ID is missing or invalid")
    return f"act_{value}"


def _configured_account_id(client: object) -> str:
    credentials = getattr(client, "credentials", None)
    account_id = getattr(credentials, "ad_account_id", None)
    return _normalize_account_id(account_id, source="Configured")


def _validate_campaign_budget_target(
    campaign: dict[str, object],
    *,
    campaign_id: str,
    configured_account_id: str,
) -> dict[str, object]:
    returned_campaign_id = str(campaign.get("id") or "").strip()
    if returned_campaign_id != campaign_id:
        raise ConfigError(
            f"Campaign lookup returned ID {returned_campaign_id or 'missing'}, "
            f"not requested ID {campaign_id}"
        )

    campaign_account_id = _normalize_account_id(
        campaign.get("account_id"), source="Campaign ownership"
    )
    if campaign_account_id != configured_account_id:
        raise ConfigError(
            f"Campaign {campaign_id} belongs to {campaign_account_id}, "
            f"not configured account {configured_account_id}"
        )

    raw_daily_budget = campaign.get("daily_budget")
    try:
        current_daily_budget = int(str(raw_daily_budget))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Campaign {campaign_id} does not have a valid raw daily budget"
        ) from None
    if current_daily_budget < 1:
        raise ConfigError(f"Campaign {campaign_id} does not have a valid raw daily budget")

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.get("name"),
        "account_id": campaign_account_id,
        "status": campaign.get("status"),
        "configured_status": campaign.get("configured_status"),
        "effective_status": campaign.get("effective_status"),
        "current_daily_budget": current_daily_budget,
        "lifetime_budget": campaign.get("lifetime_budget"),
    }


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
    bid_strategy: Optional[str] = None,
    bid_amount: Optional[int] = None,
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
        bid_strategy=bid_strategy,
        bid_amount=bid_amount,
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

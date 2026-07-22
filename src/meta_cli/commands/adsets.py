from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import typer
import yaml

from meta_cli.cli_utils import build_client, handle_cli_error, require_confirmation
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table
from meta_cli.schemas import AdSetCreateConfig, load_yaml_model

app = typer.Typer(help="Ad set operations")

ADSET_FIELDS = [
    "id",
    "name",
    "status",
    "campaign_id",
    "is_dynamic_creative",
    "optimization_goal",
    "billing_event",
    "daily_budget",
    "lifetime_budget",
    "start_time",
    "end_time",
]

ADSET_DETAIL_FIELDS = [
    "id",
    "name",
    "status",
    "configured_status",
    "effective_status",
    "campaign_id",
    "is_dynamic_creative",
    "optimization_goal",
    "billing_event",
    "promoted_object",
    "bid_strategy",
    "bid_amount",
    "daily_budget",
    "lifetime_budget",
    "budget_remaining",
    "start_time",
    "end_time",
    "targeting",
    "destination_type",
    "attribution_spec",
    "learning_stage_info",
    "issues_info",
    "recommendations",
    "review_feedback",
    "created_time",
    "updated_time",
]


@app.command("list")
def list_adsets(
    campaign_id: str = typer.Option(..., "--campaign-id", help="Campaign ID"),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    limit: int = typer.Option(100, min=1, max=1000, help="Maximum rows per request page"),
    after: Optional[str] = typer.Option(None, "--after", help="Cursor to fetch next page from"),
    before: Optional[str] = typer.Option(None, "--before", help="Cursor to fetch previous page from"),
    paginate: bool = typer.Option(True, "--paginate/--no-paginate", help="Auto-follow pagination"),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", min=1, help="Maximum pages to fetch"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        result = client.list_adsets(
            campaign_id=campaign_id,
            fields=ADSET_FIELDS,
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

        adsets = result
        rows = [
            [
                item.get("id"),
                item.get("name"),
                item.get("status"),
                item.get("campaign_id"),
                item.get("optimization_goal"),
                item.get("billing_event"),
                item.get("daily_budget"),
                item.get("lifetime_budget"),
            ]
            for item in adsets
        ]
        print_table(
            f"Ad Sets for Campaign {campaign_id}",
            ["ID", "Name", "Status", "Campaign", "Optimization", "Billing", "Daily", "Lifetime"],
            rows,
            json_output,
            adsets,
        )
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("get")
def get_adset(
    adset_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        adset = client.get_adset_details(adset_id, fields=ADSET_DETAIL_FIELDS)
        if json_output:
            emit(adset, as_json=True)
            return

        rows = [[key, adset.get(key)] for key in ADSET_DETAIL_FIELDS]
        print_table(f"Ad Set {adset_id}", ["Field", "Value"], rows, False)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("create")
def create_adset(
    config: Optional[str] = typer.Option(None, "--config", help="Path to ad set YAML config"),
    campaign_id: Optional[str] = typer.Option(None, "--campaign-id", help="Campaign ID"),
    name: Optional[str] = typer.Option(None, "--name", help="Ad set name"),
    daily_budget: Optional[int] = typer.Option(None, "--daily-budget", help="Daily budget in minor units"),
    lifetime_budget: Optional[int] = typer.Option(
        None, "--lifetime-budget", help="Lifetime budget in minor units"
    ),
    billing_event: Optional[str] = typer.Option(None, "--billing-event", help="Billing event"),
    optimization_goal: Optional[str] = typer.Option(
        None, "--optimization-goal", help="Optimization goal"
    ),
    bid_strategy: Optional[str] = typer.Option(None, "--bid-strategy", help="Bid strategy"),
    bid_amount: Optional[int] = typer.Option(None, "--bid-amount", help="Bid amount"),
    start_time: Optional[str] = typer.Option(None, "--start-time", help="Start time (ISO8601)"),
    end_time: Optional[str] = typer.Option(None, "--end-time", help="End time (ISO8601)"),
    targeting_json: Optional[str] = typer.Option(
        None, "--targeting-json", help="Targeting JSON string"
    ),
    promoted_object_json: Optional[str] = typer.Option(
        None, "--promoted-object-json", help="Promoted object JSON"
    ),
    is_dynamic_creative: Optional[bool] = typer.Option(
        None,
        "--dynamic-creative/--no-dynamic-creative",
        help="Enable or disable dynamic creative for the ad set",
    ),
    campaign_budget_optimization: bool = typer.Option(
        False,
        "--campaign-budget-optimization/--no-campaign-budget-optimization",
        help="Ad set inherits budget from a CBO campaign; skip the ad-set budget requirement",
    ),
    status: str = typer.Option("PAUSED", "--status", help="Ad set status"),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and print payload only"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        adset_config = _build_adset_config(
            config,
            campaign_id,
            name,
            daily_budget,
            lifetime_budget,
            billing_event,
            optimization_goal,
            bid_strategy,
            bid_amount,
            start_time,
            end_time,
            targeting_json,
            promoted_object_json,
            is_dynamic_creative,
            status,
            campaign_budget_optimization,
        )
        payload = adset_config.to_payload()
        if dry_run:
            emit({"ok": True, "dry_run": True, "payload": payload}, as_json=json_output)
            return

        client = build_client(auth_config)
        result = client.create_adset(payload)
        emit({"ok": True, "adset": result, "payload": payload}, as_json=json_output)
    except (ConfigError, APIError, ValueError, json.JSONDecodeError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("update-budget")
def update_adset_budget(
    adset_id: str,
    daily_budget: Optional[int] = typer.Option(
        None, "--daily-budget", min=1, help="New daily budget in minor units"
    ),
    lifetime_budget: Optional[int] = typer.Option(
        None, "--lifetime-budget", min=1, help="New lifetime budget in minor units"
    ),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and print payload only"),
) -> None:
    try:
        if (daily_budget is None) == (lifetime_budget is None):
            raise ValueError("Provide exactly one of --daily-budget or --lifetime-budget")
        budget = (
            {"daily_budget": daily_budget}
            if daily_budget is not None
            else {"lifetime_budget": lifetime_budget}
        )
        require_confirmation(f"Update budget for ad set {adset_id} to {budget}?", yes=yes)
        if dry_run:
            emit(
                {"ok": True, "dry_run": True, "adset_id": adset_id, "budget": budget},
                as_json=json_output,
            )
            return
        client = build_client(auth_config)
        result = client.update_adset_budget(adset_id, budget)
        emit(
            {"ok": True, "adset_id": adset_id, "budget": budget, "result": result},
            as_json=json_output,
        )
    except (ConfigError, APIError, ValueError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("update-targeting")
def update_adset_targeting(
    adset_id: str,
    targeting_json: Optional[str] = typer.Option(
        None, "--targeting-json", help="Complete targeting JSON object"
    ),
    targeting_file: Optional[str] = typer.Option(
        None,
        "--targeting-file",
        help="JSON/YAML file containing targeting or an ad set config with a targeting key",
    ),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and print payload only"),
) -> None:
    try:
        targeting = _load_targeting_update(targeting_json, targeting_file)
        require_confirmation(f"Replace targeting for ad set {adset_id}?", yes=yes)
        if dry_run:
            emit(
                {
                    "ok": True,
                    "dry_run": True,
                    "adset_id": adset_id,
                    "targeting": targeting,
                },
                as_json=json_output,
            )
            return
        client = build_client(auth_config)
        result = client.update_adset_targeting(adset_id, targeting)
        emit(
            {"ok": True, "adset_id": adset_id, "targeting": targeting, "result": result},
            as_json=json_output,
        )
    except (ConfigError, APIError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("pause")
def pause_adset(
    adset_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show action without updating"),
) -> None:
    _change_status(adset_id, "PAUSED", auth_config, yes, json_output, dry_run)


@app.command("resume")
def resume_adset(
    adset_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show action without updating"),
) -> None:
    _change_status(adset_id, "ACTIVE", auth_config, yes, json_output, dry_run)


def _build_adset_config(
    config_path: Optional[str],
    campaign_id: Optional[str],
    name: Optional[str],
    daily_budget: Optional[int],
    lifetime_budget: Optional[int],
    billing_event: Optional[str],
    optimization_goal: Optional[str],
    bid_strategy: Optional[str],
    bid_amount: Optional[int],
    start_time: Optional[str],
    end_time: Optional[str],
    targeting_json: Optional[str],
    promoted_object_json: Optional[str],
    is_dynamic_creative: Optional[bool],
    status: str,
    campaign_budget_optimization: bool = False,
) -> AdSetCreateConfig:
    if config_path:
        return load_yaml_model(config_path, AdSetCreateConfig)

    targeting: Dict[str, Any] = json.loads(targeting_json) if targeting_json else {}
    promoted_object: Optional[Dict[str, Any]] = (
        json.loads(promoted_object_json) if promoted_object_json else None
    )

    return AdSetCreateConfig(
        campaign_id=campaign_id,
        name=name,
        daily_budget=daily_budget,
        lifetime_budget=lifetime_budget,
        billing_event=billing_event,
        optimization_goal=optimization_goal,
        bid_strategy=bid_strategy,
        bid_amount=bid_amount,
        start_time=start_time,
        end_time=end_time,
        targeting=targeting,
        promoted_object=promoted_object,
        is_dynamic_creative=is_dynamic_creative,
        status=status,
        campaign_budget_optimization=campaign_budget_optimization,
    )


def _load_targeting_update(
    targeting_json: Optional[str], targeting_file: Optional[str]
) -> Dict[str, Any]:
    if bool(targeting_json) == bool(targeting_file):
        raise ValueError("Provide exactly one of --targeting-json or --targeting-file")

    if targeting_json:
        targeting = json.loads(targeting_json)
    else:
        path = Path(targeting_file)
        if not path.exists():
            raise ConfigError(f"Targeting file not found: {targeting_file}")
        payload = yaml.safe_load(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError("Targeting file must contain a mapping")
        targeting = payload.get("targeting", payload)

    if not isinstance(targeting, dict) or not targeting:
        raise ValueError("Targeting must be a non-empty JSON/YAML object")
    return targeting


def _change_status(
    adset_id: str,
    status: str,
    auth_config: Optional[str],
    yes: bool,
    json_output: bool,
    dry_run: bool,
) -> None:
    try:
        require_confirmation(f"Set ad set {adset_id} to {status}?", yes=yes)
        if dry_run:
            emit({"ok": True, "dry_run": True, "adset_id": adset_id, "status": status}, as_json=json_output)
            return
        client = build_client(auth_config)
        result = client.update_adset_status(adset_id, status)
        emit({"ok": True, "adset_id": adset_id, "status": status, "result": result}, as_json=json_output)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)

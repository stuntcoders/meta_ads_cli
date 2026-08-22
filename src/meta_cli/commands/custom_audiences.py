from __future__ import annotations

import json
from typing import Any, Dict, Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error, require_confirmation
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table

app = typer.Typer(help="Custom audience operations")

CUSTOM_AUDIENCE_FIELDS = [
    "id",
    "name",
    "subtype",
    "description",
    "approximate_count_lower_bound",
    "approximate_count_upper_bound",
    "delivery_status",
    "operation_status",
    "retention_days",
    "time_created",
    "time_updated",
]


@app.command("list")
def list_custom_audiences(
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
        result = client.list_custom_audiences(
            fields=CUSTOM_AUDIENCE_FIELDS,
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

        rows = [
            [
                item.get("id"),
                item.get("name"),
                item.get("subtype"),
                _size_label(item),
                item.get("retention_days"),
                _delivery_label(item),
            ]
            for item in result
        ]
        print_table(
            "Custom Audiences",
            ["ID", "Name", "Subtype", "Approx size", "Retention days", "Delivery"],
            rows,
            json_output,
            result,
        )
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("get")
def get_custom_audience(
    custom_audience_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        audience = client.get_custom_audience_details(
            custom_audience_id,
            fields=CUSTOM_AUDIENCE_FIELDS + ["rule", "pixel_id"],
        )
        if json_output:
            emit(audience, as_json=True)
            return

        rows = [[key, audience.get(key)] for key in audience.keys()]
        print_table(f"Custom Audience {custom_audience_id}", ["Field", "Value"], rows, False)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("create")
def create_custom_audience(
    name: str = typer.Option(..., "--name", help="Custom audience name"),
    pixel_id: Optional[str] = typer.Option(
        None, "--pixel-id", help="Pixel ID the website rule applies to"
    ),
    event: Optional[str] = typer.Option(
        None,
        "--event",
        help="Pixel event to include, such as PageView, Lead, or CompleteRegistration. "
        "Omit to include all pixel events.",
    ),
    url_contains: Optional[str] = typer.Option(
        None,
        "--url-contains",
        help="Only include events whose URL contains this string (case-insensitive)",
    ),
    retention_days: int = typer.Option(
        30, "--retention-days", min=1, max=180, help="How many days people stay in the audience"
    ),
    description: Optional[str] = typer.Option(None, "--description", help="Description"),
    rule_json: Optional[str] = typer.Option(
        None,
        "--rule-json",
        help="Full audience rule JSON object (overrides --pixel-id/--event/--url-contains/--retention-days)",
    ),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and print payload only"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        if rule_json is not None:
            rule = _parse_rule(rule_json)
        else:
            if not pixel_id or not pixel_id.strip():
                raise ValueError("--pixel-id is required unless --rule-json is provided")
            rule = _build_website_rule(
                pixel_id=pixel_id.strip(),
                event=event.strip() if event else None,
                url_contains=url_contains.strip() if url_contains else None,
                retention_days=retention_days,
            )

        payload: Dict[str, Any] = {
            "name": name.strip(),
            "subtype": "WEBSITE",
            "rule": json.dumps(rule, separators=(",", ":")),
        }
        if not payload["name"]:
            raise ValueError("--name must not be blank")
        if description is not None:
            payload["description"] = description

        require_confirmation(
            f"Create website custom audience '{payload['name']}'?",
            yes=yes,
        )
        if dry_run:
            emit({"ok": True, "dry_run": True, "payload": payload}, as_json=json_output)
            return

        client = build_client(auth_config)
        result = client.create_custom_audience(payload)
        emit({"ok": True, "custom_audience": result, "payload": payload}, as_json=json_output)
    except (ConfigError, APIError, ValueError, json.JSONDecodeError) as exc:
        handle_cli_error(exc, as_json=json_output)


def _build_website_rule(
    pixel_id: str,
    event: Optional[str],
    url_contains: Optional[str],
    retention_days: int,
) -> Dict[str, Any]:
    filters = []
    if event:
        filters.append({"field": "event", "operator": "eq", "value": event})
    if url_contains:
        filters.append({"field": "url", "operator": "i_contains", "value": url_contains})

    rule_entry: Dict[str, Any] = {
        "event_sources": [{"type": "pixel", "id": pixel_id}],
        "retention_seconds": retention_days * 86400,
    }
    if filters:
        rule_entry["filter"] = {"operator": "and", "filters": filters}

    return {"inclusions": {"operator": "or", "rules": [rule_entry]}}


def _parse_rule(rule_json: str) -> Dict[str, Any]:
    rule = json.loads(rule_json)
    if not isinstance(rule, dict) or not rule:
        raise ValueError("--rule-json must be a non-empty JSON object")
    return rule


def _size_label(item: Dict[str, Any]) -> Any:
    lower = item.get("approximate_count_lower_bound")
    upper = item.get("approximate_count_upper_bound")
    if lower is None and upper is None:
        return None
    return f"{lower}-{upper}"


def _delivery_label(item: Dict[str, Any]) -> Any:
    status = item.get("delivery_status")
    if isinstance(status, dict):
        return status.get("description") or status.get("code")
    return status

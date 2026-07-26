from __future__ import annotations

import json
from typing import Any, Dict, Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error, require_confirmation
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table

app = typer.Typer(help="Custom conversion operations")

CUSTOM_CONVERSION_FIELDS = [
    "id",
    "name",
    "description",
    "custom_event_type",
    "event_source_type",
    "pixel",
    "data_sources",
    "rule",
    "action_source_type",
    "default_conversion_value",
    "first_fired_time",
    "last_fired_time",
    "is_archived",
    "is_unavailable",
    "retention_days",
    "creation_time",
]


@app.command("list")
def list_custom_conversions(
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
        result = client.list_custom_conversions(
            fields=CUSTOM_CONVERSION_FIELDS,
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
                item.get("custom_event_type"),
                _event_source_label(item),
                item.get("last_fired_time"),
                item.get("is_unavailable"),
                item.get("is_archived"),
            ]
            for item in result
        ]
        print_table(
            "Custom Conversions",
            ["ID", "Name", "Category", "Event source", "Last fired", "Unavailable", "Archived"],
            rows,
            json_output,
            result,
        )
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("get")
def get_custom_conversion(
    custom_conversion_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        custom_conversion = client.get_custom_conversion_details(
            custom_conversion_id,
            fields=CUSTOM_CONVERSION_FIELDS,
        )
        if json_output:
            emit(custom_conversion, as_json=True)
            return

        rows = [[key, custom_conversion.get(key)] for key in CUSTOM_CONVERSION_FIELDS]
        print_table(f"Custom Conversion {custom_conversion_id}", ["Field", "Value"], rows, False)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("create")
def create_custom_conversion(
    name: str = typer.Option(..., "--name", help="Custom conversion name"),
    event_source_id: str = typer.Option(..., "--event-source-id", help="Pixel or event source ID"),
    rule_json: str = typer.Option(..., "--rule-json", help="Custom conversion rule JSON object"),
    custom_event_type: str = typer.Option(
        "OTHER",
        "--custom-event-type",
        help="Meta conversion category, such as OTHER, CONTACT, or LEAD",
    ),
    description: Optional[str] = typer.Option(None, "--description", help="Description"),
    action_source_type: Optional[str] = typer.Option(
        None,
        "--action-source-type",
        help="Action source type, such as WEBSITE",
    ),
    default_conversion_value: Optional[float] = typer.Option(
        None,
        "--default-conversion-value",
        min=0,
        help="Optional default conversion value",
    ),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and print payload only"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        rule = _parse_rule(rule_json)
        payload: Dict[str, Any] = {
            "name": name.strip(),
            "event_source_id": event_source_id.strip(),
            "rule": json.dumps(rule, separators=(",", ":")),
            "custom_event_type": custom_event_type.strip().upper(),
        }
        if not payload["name"]:
            raise ValueError("--name must not be blank")
        if not payload["event_source_id"]:
            raise ValueError("--event-source-id must not be blank")
        if description is not None:
            payload["description"] = description
        if action_source_type is not None:
            payload["action_source_type"] = action_source_type.strip().lower()
        if default_conversion_value is not None:
            payload["default_conversion_value"] = default_conversion_value

        require_confirmation(
            f"Create custom conversion '{payload['name']}' for event source {payload['event_source_id']}?",
            yes=yes,
        )
        if dry_run:
            emit({"ok": True, "dry_run": True, "payload": payload}, as_json=json_output)
            return

        client = build_client(auth_config)
        result = client.create_custom_conversion(payload)
        emit({"ok": True, "custom_conversion": result, "payload": payload}, as_json=json_output)
    except (ConfigError, APIError, ValueError, json.JSONDecodeError) as exc:
        handle_cli_error(exc, as_json=json_output)


def _event_source_label(item: Dict[str, Any]) -> Any:
    pixel = item.get("pixel")
    if isinstance(pixel, dict):
        return pixel.get("id") or pixel.get("name")
    data_sources = item.get("data_sources")
    if isinstance(data_sources, list):
        return ", ".join(
            str(source.get("id") or source.get("name"))
            for source in data_sources
            if isinstance(source, dict) and (source.get("id") or source.get("name"))
        )
    return None


def _parse_rule(rule_json: str) -> Dict[str, Any]:
    rule = json.loads(rule_json)
    if not isinstance(rule, dict) or not rule:
        raise ValueError("--rule-json must be a non-empty JSON object")
    return rule

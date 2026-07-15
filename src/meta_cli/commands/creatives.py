from __future__ import annotations

from typing import Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table
from meta_cli.schemas import AdCreateConfig, load_yaml_model

app = typer.Typer(help="Ad creative operations")

CREATIVE_DETAIL_FIELDS = [
    "id",
    "name",
    "object_story_spec",
    "asset_feed_spec",
    "effective_object_story_id",
    "status",
]


@app.command("create")
def create_creative(
    config: str = typer.Option(..., "--config", help="Path to ad YAML config to build the creative from"),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and print payload only"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        ad_config = load_yaml_model(config, AdCreateConfig)
        if ad_config.existing_creative_id:
            raise ValueError("Config uses existing_creative_id; no creative payload is required")
        creative_payload = ad_config.build_creative_payload()

        if dry_run:
            emit(
                {
                    "ok": True,
                    "dry_run": True,
                    "uses_asset_feed_spec": ad_config.uses_asset_feed_spec(),
                    "creative_payload": creative_payload,
                },
                as_json=json_output,
            )
            return

        client = build_client(auth_config)
        creative_result = client.create_creative(creative_payload)
        emit(
            {
                "ok": True,
                "creative": creative_result,
                "uses_asset_feed_spec": ad_config.uses_asset_feed_spec(),
            },
            as_json=json_output,
        )
    except (ConfigError, APIError, ValueError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("get")
def get_creative(
    creative_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        creative = client.get_creative_details(creative_id, fields=CREATIVE_DETAIL_FIELDS)
        if json_output:
            emit(creative, as_json=True)
            return

        rows = [[key, creative.get(key)] for key in CREATIVE_DETAIL_FIELDS]
        print_table(f"Creative {creative_id}", ["Field", "Value"], rows, False)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)

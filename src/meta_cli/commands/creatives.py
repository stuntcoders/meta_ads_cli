from __future__ import annotations

from typing import Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table

app = typer.Typer(help="Ad creative operations")

CREATIVE_DETAIL_FIELDS = [
    "id",
    "name",
    "object_story_spec",
    "asset_feed_spec",
    "effective_object_story_id",
    "status",
]


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

from __future__ import annotations

from typing import Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table

app = typer.Typer(help="Targeting discovery operations")


@app.command("search-interests")
def search_interests(
    query: str = typer.Option(..., "--query", "-q", help="Interest name to search"),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        interests = client.search_targeting_interests(query=query)
        if json_output:
            emit({"data": interests}, as_json=True)
            return

        rows = [
            [
                item.get("id"),
                item.get("name"),
                item.get("audience_size_lower_bound") or item.get("audience_size"),
                item.get("audience_size_upper_bound"),
                " > ".join(item.get("path", [])),
            ]
            for item in interests
        ]
        print_table(
            f"Targeting interests for {query}",
            ["ID", "Name", "Audience low", "Audience high", "Path"],
            rows,
            False,
        )
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("search-locations")
def search_locations(
    query: str = typer.Option(..., "--query", "-q", help="Location name to search"),
    country: Optional[str] = typer.Option(
        None, "--country", help="Optional ISO country code, for example IN"
    ),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        countries = [country.upper()] if country else None
        locations = client.search_targeting_locations(query=query, countries=countries)
        if json_output:
            emit({"data": locations}, as_json=True)
            return

        rows = [
            [
                item.get("key"),
                item.get("name"),
                item.get("type"),
                item.get("country_code"),
                item.get("region"),
            ]
            for item in locations
        ]
        print_table(
            f"Targeting locations for {query}",
            ["Key", "Name", "Type", "Country", "Region"],
            rows,
            False,
        )
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)

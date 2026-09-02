from __future__ import annotations

from typing import Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table

app = typer.Typer(help="Targeting discovery operations")

TARGETING_CATEGORY_CLASSES = {
    "demographics",
    "ethnic_affinity",
    "family_statuses",
    "generation",
    "home_ownership",
    "home_type",
    "home_value",
    "household_composition",
    "income",
    "industries",
    "life_events",
    "markets",
    "moms",
    "net_worth",
    "office_type",
    "politics",
    "user_device",
    "user_os",
}


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


@app.command("search-categories")
def search_categories(
    demographic_class: str = typer.Option(
        ...,
        "--class",
        help="Meta targeting category class, such as family_statuses or demographics",
    ),
    query: Optional[str] = typer.Option(
        None,
        "--query",
        "-q",
        help="Optional case-insensitive name/path filter applied to returned categories",
    ),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        normalized_class = demographic_class.strip().lower()
        if normalized_class not in TARGETING_CATEGORY_CLASSES:
            allowed = ", ".join(sorted(TARGETING_CATEGORY_CLASSES))
            raise ValueError(f"Unsupported targeting category class '{demographic_class}'. Use: {allowed}")
        client = build_client(auth_config)
        categories = client.search_targeting_categories(demographic_class=normalized_class)
        if query:
            needle = query.casefold()
            categories = [
                item
                for item in categories
                if needle
                in " ".join(
                    [
                        str(item.get("name", "")),
                        str(item.get("description", "")),
                        " ".join(item.get("path", [])),
                    ]
                ).casefold()
            ]
        if json_output:
            emit({"class": normalized_class, "query": query, "data": categories}, as_json=True)
            return

        rows = [
            [
                item.get("id"),
                item.get("name"),
                item.get("type"),
                " > ".join(item.get("path", [])),
                item.get("description"),
            ]
            for item in categories
        ]
        title = f"Targeting categories for {normalized_class}"
        if query:
            title += f" matching {query}"
        print_table(title, ["ID", "Name", "Type", "Path", "Description"], rows, False)
    except (ConfigError, APIError, ValueError) as exc:
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

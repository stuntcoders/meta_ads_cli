from __future__ import annotations

from typing import Any, Dict, Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import print_table

app = typer.Typer(help="Insights and performance reporting")

AD_INSIGHT_FIELDS = [
    "ad_id",
    "ad_name",
    "adset_id",
    "adset_name",
    "campaign_id",
    "campaign_name",
    "impressions",
    "reach",
    "clicks",
    "inline_link_clicks",
    "ctr",
    "cpc",
    "spend",
    "actions",
    "cost_per_action_type",
    "date_start",
    "date_stop",
]

DEFAULT_RESULT_ACTION_TYPES = ["purchase", "offsite_conversion", "lead", "complete_registration"]
DEFAULT_COST_ACTION_TYPES = [
    "purchase",
    "offsite_conversion",
    "lead",
    "complete_registration",
    "link_click",
]


@app.command("ads")
def ads_insights(
    adset_id: Optional[str] = typer.Option(None, "--adset-id", help="Ad set ID"),
    all_ads: bool = typer.Option(False, "--all", help="Use account-wide ad insights"),
    date_preset: Optional[str] = typer.Option(
        "last_7d", "--date-preset", help="Meta date preset, e.g. last_7d"
    ),
    since: Optional[str] = typer.Option(None, "--since", help="Start date YYYY-MM-DD"),
    until: Optional[str] = typer.Option(None, "--until", help="End date YYYY-MM-DD"),
    result_action_types: str = typer.Option(
        ",".join(DEFAULT_RESULT_ACTION_TYPES),
        "--result-action-types",
        help="Comma-separated action types to treat as conversions",
    ),
    cost_action_types: str = typer.Option(
        ",".join(DEFAULT_COST_ACTION_TYPES),
        "--cost-action-types",
        help="Comma-separated action types to use for cost per result",
    ),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    limit: int = typer.Option(200, min=1, max=2000, help="Maximum rows per request page"),
    after: Optional[str] = typer.Option(None, "--after", help="Cursor to fetch next page from"),
    before: Optional[str] = typer.Option(None, "--before", help="Cursor to fetch previous page from"),
    paginate: bool = typer.Option(True, "--paginate/--no-paginate", help="Auto-follow pagination"),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", min=1, help="Maximum pages to fetch"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        if not all_ads and not adset_id:
            raise ValueError("Provide --all or --adset-id")
        if all_ads and adset_id:
            raise ValueError("Use either --all or --adset-id, not both")
        if since or until:
            date_preset = None

        conversion_keys = _parse_action_keys(result_action_types)
        cost_keys = _parse_action_keys(cost_action_types)

        client = build_client(auth_config)
        insights = client.get_ad_insights(
            fields=AD_INSIGHT_FIELDS,
            date_preset=date_preset,
            since=since,
            until=until,
            adset_id=adset_id,
            limit=limit,
            after=after,
            before=before,
            auto_paginate=paginate,
            max_pages=max_pages,
        )
        rows = [
            _insight_row(item, conversion_action_types=conversion_keys, cost_action_types=cost_keys)
            for item in insights
        ]
        print_table(
            "Ad Insights",
            [
                "Ad ID",
                "Ad Name",
                "Impressions",
                "Reach",
                "Clicks",
                "Link Clicks",
                "CTR",
                "CPC",
                "Spend",
                "Conversions",
                "Cost/Result",
                "Date Start",
                "Date Stop",
            ],
            rows,
            json_output,
            insights,
        )
    except (ConfigError, APIError, ValueError) as exc:
        handle_cli_error(exc, as_json=json_output)


def _parse_action_keys(raw: str) -> list[str]:
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    if not keys:
        raise ValueError("At least one action type must be provided")
    return keys


def _extract_action_value(actions: Any, keys: list[str]) -> str:
    if not isinstance(actions, list):
        return ""
    for item in actions:
        if item.get("action_type") in keys:
            return str(item.get("value", ""))
    return ""


def _insight_row(
    item: Dict[str, Any],
    conversion_action_types: list[str] | None = None,
    cost_action_types: list[str] | None = None,
) -> list[str]:
    conversion_keys = conversion_action_types or DEFAULT_RESULT_ACTION_TYPES
    cost_keys = cost_action_types or DEFAULT_COST_ACTION_TYPES

    conversions = _extract_action_value(item.get("actions"), conversion_keys)
    cost_per_result = _extract_action_value(item.get("cost_per_action_type"), cost_keys)
    link_clicks = str(item.get("inline_link_clicks", "")) or _extract_action_value(
        item.get("actions"), ["link_click", "offsite_conversion.fb_pixel_click"]
    )

    return [
        str(item.get("ad_id", "")),
        str(item.get("ad_name", "")),
        str(item.get("impressions", "")),
        str(item.get("reach", "")),
        str(item.get("clicks", "")),
        link_clicks,
        str(item.get("ctr", "")),
        str(item.get("cpc", "")),
        str(item.get("spend", "")),
        conversions,
        cost_per_result,
        str(item.get("date_start", "")),
        str(item.get("date_stop", "")),
    ]

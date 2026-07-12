from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table

app = typer.Typer(help="Read-only account snapshots and recurring reports")

ACCOUNT_FIELDS = [
    "id",
    "name",
    "account_status",
    "currency",
    "timezone_name",
    "timezone_offset_hours_utc",
    "business_name",
    "amount_spent",
    "balance",
    "spend_cap",
    "disable_reason",
    "created_time",
]
CAMPAIGN_FIELDS = [
    "id",
    "name",
    "status",
    "effective_status",
    "objective",
    "daily_budget",
    "lifetime_budget",
    "start_time",
    "stop_time",
]
ADSET_FIELDS = [
    "id",
    "name",
    "status",
    "effective_status",
    "campaign_id",
    "optimization_goal",
    "billing_event",
    "daily_budget",
    "lifetime_budget",
    "start_time",
    "end_time",
]
AD_FIELDS = [
    "id",
    "name",
    "status",
    "effective_status",
    "campaign_id",
    "adset_id",
    "creative",
    "created_time",
    "updated_time",
]
INSIGHT_FIELDS = [
    "account_id",
    "account_name",
    "impressions",
    "reach",
    "frequency",
    "clicks",
    "inline_link_clicks",
    "ctr",
    "cpc",
    "cpm",
    "spend",
    "actions",
    "cost_per_action_type",
    "date_start",
    "date_stop",
]

PERIOD_PRESETS = {
    "today": "today",
    "yesterday": "yesterday",
    "7d": "last_7d",
    "30d": "last_30d",
    "lifetime": "maximum",
}
DEFAULT_PERIODS = "today,yesterday,7d,30d,lifetime"


@app.command("account")
def account_report(
    periods: str = typer.Option(
        DEFAULT_PERIODS,
        "--periods",
        help="Comma-separated periods: today, yesterday, 7d, 30d, lifetime",
    ),
    auth_config: Optional[str] = typer.Option(
        None,
        "--auth-config",
        help="Path to auth YAML (defaults to standard CLI auth configuration)",
    ),
    limit: int = typer.Option(
        200,
        min=1,
        max=2000,
        help="Maximum entity rows per Meta API request page; all pages are read",
    ),
    max_pages: Optional[int] = typer.Option(
        None,
        "--max-pages",
        min=1,
        help="Optional maximum pages for each entity collection",
    ),
    output_file: Optional[str] = typer.Option(
        None,
        "--output-file",
        help="Write the complete structured JSON report, e.g. reports/account.json",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output the complete report as JSON"),
) -> None:
    """Collect a read-only account snapshot and recurring period insights.

    Uses the configured Meta credentials and ad account. No objects are changed.
    """
    try:
        selected_periods = _parse_periods(periods)
        client = build_client(auth_config)

        account = client.get_account_details(fields=ACCOUNT_FIELDS)
        campaigns = client.list_campaigns(
            fields=CAMPAIGN_FIELDS,
            limit=limit,
            auto_paginate=True,
            max_pages=max_pages,
        )
        adsets = client.list_all_adsets(
            fields=ADSET_FIELDS,
            limit=limit,
            auto_paginate=True,
            max_pages=max_pages,
        )
        ads = client.list_all_ads(
            fields=AD_FIELDS,
            limit=limit,
            auto_paginate=True,
            max_pages=max_pages,
        )
        insights = [
            {
                "period": period,
                "date_preset": PERIOD_PRESETS[period],
                "data": client.get_account_insights(
                    fields=INSIGHT_FIELDS,
                    date_preset=PERIOD_PRESETS[period],
                ),
            }
            for period in selected_periods
        ]

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "read_only": True,
            "account": account,
            "summary": {
                "campaigns": _entity_summary(campaigns),
                "adsets": _entity_summary(adsets),
                "ads": _entity_summary(ads),
            },
            "campaigns": campaigns,
            "adsets": adsets,
            "ads": ads,
            "insights": insights,
        }

        if output_file:
            _write_report(output_file, report)

        if json_output:
            emit(report, as_json=True)
            return

        print_table(
            "Account Snapshot",
            ["Account ID", "Name", "Status", "Currency", "Timezone"],
            [[
                account.get("id"),
                account.get("name"),
                account.get("account_status"),
                account.get("currency"),
                account.get("timezone_name"),
            ]],
        )
        print_table(
            "Entity Summary",
            ["Entity", "Total", "Active", "Paused", "Other"],
            [
                [name, values["total"], values["active"], values["paused"], values["other"]]
                for name, values in report["summary"].items()
            ],
        )
        print_table(
            "Period Insights",
            ["Period", "Start", "Stop", "Spend", "Impressions", "Reach", "Clicks", "CTR"],
            [_insight_table_row(item) for item in insights],
        )
        if output_file:
            emit(f"Saved JSON report to {output_file}")
    except (ConfigError, APIError, ValueError, OSError) as exc:
        handle_cli_error(exc, as_json=json_output)


def _parse_periods(raw: str) -> list[str]:
    periods: list[str] = []
    for value in raw.split(","):
        period = value.strip().lower()
        if not period:
            continue
        if period not in PERIOD_PRESETS:
            allowed = ", ".join(PERIOD_PRESETS)
            raise ValueError(f"Unsupported period '{period}'. Choose from: {allowed}")
        if period not in periods:
            periods.append(period)
    if not periods:
        raise ValueError("At least one reporting period must be provided")
    return periods


def _entity_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": len(rows), "active": 0, "paused": 0, "other": 0}
    for row in rows:
        status = str(row.get("effective_status") or row.get("status") or "").upper()
        if status == "ACTIVE":
            summary["active"] += 1
        elif status == "PAUSED":
            summary["paused"] += 1
        else:
            summary["other"] += 1
    return summary


def _insight_table_row(period_data: dict[str, Any]) -> list[Any]:
    rows = period_data["data"]
    row = rows[0] if rows else {}
    return [
        period_data["period"],
        row.get("date_start"),
        row.get("date_stop"),
        row.get("spend"),
        row.get("impressions"),
        row.get("reach"),
        row.get("clicks"),
        row.get("ctr"),
    ]


def _write_report(output_file: str, report: dict[str, Any]) -> None:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

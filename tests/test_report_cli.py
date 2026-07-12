from __future__ import annotations

import json

from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.exceptions import APIError

runner = CliRunner()


class FakeReportClient:
    def __init__(self):
        self.insight_presets: list[str] = []
        self.calls: list[str] = []

    def get_account_details(self, **kwargs):
        self.calls.append("account")
        assert "currency" in kwargs["fields"]
        return {
            "id": "act_123",
            "name": "MentorMaam",
            "account_status": 1,
            "currency": "USD",
            "timezone_name": "Europe/Sofia",
        }

    def list_campaigns(self, **kwargs):
        self.calls.append("campaigns")
        assert kwargs["auto_paginate"] is True
        return [{"id": "c1", "name": "Campaign", "effective_status": "ACTIVE"}]

    def list_all_adsets(self, **kwargs):
        self.calls.append("adsets")
        return [
            {
                "id": "s1",
                "name": "Ad Set",
                "campaign_id": "c1",
                "effective_status": "PAUSED",
            }
        ]

    def list_all_ads(self, **kwargs):
        self.calls.append("ads")
        return [
            {
                "id": "a1",
                "name": "Ad",
                "campaign_id": "c1",
                "adset_id": "s1",
                "effective_status": "ACTIVE",
            }
        ]

    def get_account_insights(self, **kwargs):
        preset = kwargs["date_preset"]
        self.calls.append(f"insights:{preset}")
        self.insight_presets.append(preset)
        assert "spend" in kwargs["fields"]
        return [
            {
                "account_id": "act_123",
                "spend": "12.34",
                "impressions": "1000",
                "reach": "800",
                "clicks": "25",
                "ctr": "2.5",
                "date_start": "2026-07-01",
                "date_stop": "2026-07-07",
            }
        ]


def test_account_report_json_contains_snapshot_entities_and_period_rows(monkeypatch):
    fake = FakeReportClient()
    monkeypatch.setattr("meta_cli.commands.report.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        ["report", "account", "--periods", "today,7d,lifetime", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["read_only"] is True
    assert payload["account"]["id"] == "act_123"
    assert payload["campaigns"][0]["id"] == "c1"
    assert payload["adsets"][0]["id"] == "s1"
    assert payload["ads"][0]["id"] == "a1"
    assert [row["period"] for row in payload["insights"]] == ["today", "7d", "lifetime"]
    assert payload["insights"][1]["data"][0]["spend"] == "12.34"
    assert fake.insight_presets == ["today", "last_7d", "maximum"]
    assert fake.calls[:4] == ["account", "campaigns", "adsets", "ads"]


def test_account_report_defaults_to_all_recurring_periods_and_writes_json(monkeypatch, tmp_path):
    fake = FakeReportClient()
    monkeypatch.setattr("meta_cli.commands.report.build_client", lambda *_: fake)
    output_path = tmp_path / "reports" / "account.json"

    result = runner.invoke(
        app,
        ["report", "account", "--output-file", str(output_path), "--max-pages", "2"],
    )

    assert result.exit_code == 0
    assert "Saved JSON report" in result.stdout
    payload = json.loads(output_path.read_text())
    assert [row["period"] for row in payload["insights"]] == [
        "today",
        "yesterday",
        "7d",
        "30d",
        "lifetime",
    ]
    assert payload["summary"]["campaigns"] == {
        "total": 1,
        "active": 1,
        "paused": 0,
        "other": 0,
    }
    assert fake.insight_presets == ["today", "yesterday", "last_7d", "last_30d", "maximum"]


def test_account_report_rejects_unknown_period_before_auth(monkeypatch):
    def fail_if_called(*_args):
        raise AssertionError("client must not be built for invalid arguments")

    monkeypatch.setattr("meta_cli.commands.report.build_client", fail_if_called)
    result = runner.invoke(app, ["report", "account", "--periods", "weekly", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "Unsupported period 'weekly'" in payload["error"]


def test_account_report_surfaces_api_errors_as_json(monkeypatch):
    class FailingClient(FakeReportClient):
        def get_account_details(self, **kwargs):
            raise APIError("account access denied")

    monkeypatch.setattr("meta_cli.commands.report.build_client", lambda *_: FailingClient())
    result = runner.invoke(app, ["report", "account", "--periods", "today", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"ok": False, "error": "account access denied"}


def test_account_report_help_documents_auth_periods_output_and_read_only():
    result = runner.invoke(app, ["report", "account", "--help"])

    assert result.exit_code == 0
    assert "read-only" in result.stdout
    assert "today, yesterday, 7d, 30d," in result.stdout
    assert "lifetime" in result.stdout
    assert "auth YAML" in result.stdout
    assert "structured JSON report" in result.stdout

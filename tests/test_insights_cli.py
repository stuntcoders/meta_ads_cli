from __future__ import annotations

from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.commands.insights import _insight_row, _parse_action_keys

runner = CliRunner()


class FakeInsightsClient:
    def __init__(self):
        self.last_kwargs = {}

    def get_ad_insights(self, **kwargs):
        self.last_kwargs = kwargs
        assert kwargs["date_preset"] == "last_7d"
        data = [
            {
                "ad_id": "1",
                "ad_name": "Ad",
                "impressions": "100",
                "reach": "80",
                "clicks": "10",
                "inline_link_clicks": "5",
                "ctr": "10",
                "cpc": "0.5",
                "spend": "5",
                "actions": [{"action_type": "purchase", "value": "2"}],
                "cost_per_action_type": [{"action_type": "purchase", "value": "2.5"}],
                "date_start": "2026-03-01",
                "date_stop": "2026-03-07",
            }
        ]
        if kwargs.get("include_paging"):
            return {"data": data, "paging": {"next_after": "ins_next", "has_more": True}}
        return data


def test_parse_action_keys_requires_values():
    try:
        _parse_action_keys("  ,  ")
    except ValueError as exc:
        assert "At least one action type" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_insight_row_extracts_conversion_and_cost():
    row = _insight_row(
        {
            "ad_id": "1",
            "ad_name": "Test",
            "actions": [{"action_type": "purchase", "value": "3"}],
            "cost_per_action_type": [{"action_type": "purchase", "value": "1.25"}],
        }
    )
    assert row[9] == "3"
    assert row[10] == "1.25"


def test_insight_row_uses_custom_action_mapping():
    row = _insight_row(
        {
            "ad_id": "1",
            "ad_name": "Test",
            "actions": [{"action_type": "lead", "value": "4"}],
            "cost_per_action_type": [{"action_type": "lead", "value": "0.75"}],
        },
        conversion_action_types=["lead"],
        cost_action_types=["lead"],
    )
    assert row[9] == "4"
    assert row[10] == "0.75"


def test_insights_ads_all_json(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.insights.build_client", lambda *_: FakeInsightsClient())
    result = runner.invoke(app, ["insights", "ads", "--all", "--json"])
    assert result.exit_code == 0
    assert '"ad_id": "1"' in result.stdout
    assert '"next_after": "ins_next"' in result.stdout


def test_insights_passes_pagination_options(monkeypatch):
    fake = FakeInsightsClient()
    monkeypatch.setattr("meta_cli.commands.insights.build_client", lambda *_: fake)
    result = runner.invoke(
        app,
        [
            "insights",
            "ads",
            "--all",
            "--after",
            "cursor_2",
            "--no-paginate",
            "--result-action-types",
            "lead,purchase",
            "--cost-action-types",
            "lead",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert fake.last_kwargs["after"] == "cursor_2"
    assert fake.last_kwargs["auto_paginate"] is False


def test_insights_output_file_json(monkeypatch, tmp_path):
    output_path = tmp_path / "insights.json"
    monkeypatch.setattr("meta_cli.commands.insights.build_client", lambda *_: FakeInsightsClient())
    result = runner.invoke(
        app,
        ["insights", "ads", "--all", "--output-file", str(output_path), "--output-format", "json", "--json"],
    )
    assert result.exit_code == 0
    payload = output_path.read_text()
    assert '"paging"' in payload
    assert '"meta"' in payload


def test_insights_output_file_csv(monkeypatch, tmp_path):
    output_path = tmp_path / "insights.csv"
    monkeypatch.setattr("meta_cli.commands.insights.build_client", lambda *_: FakeInsightsClient())
    result = runner.invoke(
        app,
        ["insights", "ads", "--all", "--output-file", str(output_path), "--output-format", "csv", "--json"],
    )
    assert result.exit_code == 0
    content = output_path.read_text()
    assert "ad_id,ad_name" in content
    assert "1,Ad" in content

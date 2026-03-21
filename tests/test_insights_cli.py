from __future__ import annotations

from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.commands.insights import _insight_row

runner = CliRunner()


class FakeInsightsClient:
    def get_ad_insights(self, **kwargs):
        assert kwargs["date_preset"] == "last_7d"
        return [
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


def test_insights_ads_all_json(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.insights.build_client", lambda *_: FakeInsightsClient())
    result = runner.invoke(app, ["insights", "ads", "--all", "--json"])
    assert result.exit_code == 0
    assert '"ad_id": "1"' in result.stdout

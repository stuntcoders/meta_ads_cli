from __future__ import annotations

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeClient:
    def list_campaigns(self, fields, limit):
        assert "id" in fields
        return [
            {
                "id": "1",
                "name": "Camp 1",
                "status": "PAUSED",
                "objective": "LINK_CLICKS",
                "daily_budget": "1000",
                "lifetime_budget": None,
            }
        ]

    def update_campaign_status(self, campaign_id, status):
        return {"id": campaign_id, "status": status}


def test_campaigns_list_json(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.campaigns.build_client", lambda *_: FakeClient())
    result = runner.invoke(app, ["campaigns", "list", "--json"])
    assert result.exit_code == 0
    assert '"id": "1"' in result.stdout


def test_campaign_pause_dry_run(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.campaigns.build_client", lambda *_: FakeClient())
    result = runner.invoke(app, ["campaigns", "pause", "123", "--yes", "--dry-run", "--json"])
    assert result.exit_code == 0
    assert '"dry_run": true' in result.stdout.lower()

from __future__ import annotations

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeAdSetClient:
    def list_adsets(self, campaign_id, fields, limit):
        return [{"id": "a1", "name": "A1", "status": "PAUSED", "campaign_id": campaign_id}]

    def create_adset(self, payload):
        return {"id": "new_adset", **payload}

    def update_adset_status(self, adset_id, status):
        return {"id": adset_id, "status": status}


def test_adsets_create_dry_run_with_flags(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.adsets.build_client", lambda *_: FakeAdSetClient())
    result = runner.invoke(
        app,
        [
            "adsets",
            "create",
            "--campaign-id",
            "123",
            "--name",
            "Test Adset",
            "--daily-budget",
            "1000",
            "--targeting-json",
            '{"geo_locations": {"countries": ["US"]}}',
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert '"campaign_id": "123"' in result.stdout


def test_adsets_pause_dry_run(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.adsets.build_client", lambda *_: FakeAdSetClient())
    result = runner.invoke(app, ["adsets", "pause", "a1", "--yes", "--dry-run", "--json"])
    assert result.exit_code == 0
    assert '"status": "PAUSED"' in result.stdout

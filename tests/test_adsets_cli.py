from __future__ import annotations

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeAdSetClient:
    def __init__(self):
        self.last_list_kwargs = {}

    def list_adsets(
        self,
        campaign_id,
        fields,
        limit,
        after=None,
        before=None,
        auto_paginate=True,
        max_pages=None,
    ):
        self.last_list_kwargs = {
            "campaign_id": campaign_id,
            "after": after,
            "before": before,
            "auto_paginate": auto_paginate,
            "max_pages": max_pages,
            "limit": limit,
        }
        return [{"id": "a1", "name": "A1", "status": "PAUSED", "campaign_id": campaign_id}]

    def create_adset(self, payload):
        return {"id": "new_adset", **payload}

    def update_adset_status(self, adset_id, status):
        return {"id": adset_id, "status": status}


def test_adsets_list_pagination_flags(monkeypatch):
    fake = FakeAdSetClient()
    monkeypatch.setattr("meta_cli.commands.adsets.build_client", lambda *_: fake)
    result = runner.invoke(
        app,
        [
            "adsets",
            "list",
            "--campaign-id",
            "123",
            "--before",
            "prev_1",
            "--no-paginate",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert fake.last_list_kwargs["before"] == "prev_1"
    assert fake.last_list_kwargs["auto_paginate"] is False


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

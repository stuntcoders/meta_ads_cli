from __future__ import annotations

import json

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeAdSetClient:
    def __init__(self):
        self.last_list_kwargs = {}
        self.last_get_adset = None
        self.last_targeting_update = None

    def list_adsets(
        self,
        campaign_id,
        fields,
        limit,
        after=None,
        before=None,
        auto_paginate=True,
        max_pages=None,
        include_paging=False,
    ):
        self.last_list_kwargs = {
            "campaign_id": campaign_id,
            "after": after,
            "before": before,
            "auto_paginate": auto_paginate,
            "max_pages": max_pages,
            "limit": limit,
            "include_paging": include_paging,
        }
        data = [{"id": "a1", "name": "A1", "status": "PAUSED", "campaign_id": campaign_id}]
        if include_paging:
            return {"data": data, "paging": {"next_after": "next_adset"}}
        return data

    def get_adset_details(self, adset_id, fields):
        self.last_get_adset = {"adset_id": adset_id, "fields": fields}
        return {
            "id": adset_id,
            "name": "A1",
            "status": "PAUSED",
            "campaign_id": "123",
            "promoted_object": {
                "pixel_id": "pixel_456",
                "custom_event_type": "COMPLETE_REGISTRATION",
            },
        }

    def create_adset(self, payload):
        return {"id": "new_adset", **payload}

    def update_adset_status(self, adset_id, status):
        return {"id": adset_id, "status": status}

    def update_adset_targeting(self, adset_id, targeting):
        self.last_targeting_update = {"adset_id": adset_id, "targeting": targeting}
        return {"id": adset_id}


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
    assert '"paging"' in result.stdout
    assert '"next_after": "next_adset"' in result.stdout


def test_adsets_get_json(monkeypatch):
    fake = FakeAdSetClient()
    monkeypatch.setattr("meta_cli.commands.adsets.build_client", lambda *_: fake)
    result = runner.invoke(app, ["adsets", "get", "a1", "--json"])

    assert result.exit_code == 0
    assert '"id": "a1"' in result.stdout
    assert '"promoted_object"' in result.stdout
    assert '"pixel_id": "pixel_456"' in result.stdout
    assert '"custom_event_type": "COMPLETE_REGISTRATION"' in result.stdout
    assert fake.last_get_adset is not None
    assert fake.last_get_adset["adset_id"] == "a1"
    assert "targeting" in fake.last_get_adset["fields"]
    assert "promoted_object" in fake.last_get_adset["fields"]


def test_adsets_get_normal_output_includes_promoted_object(monkeypatch):
    fake = FakeAdSetClient()
    monkeypatch.setattr("meta_cli.commands.adsets.build_client", lambda *_: fake)
    result = runner.invoke(app, ["adsets", "get", "a1"])

    assert result.exit_code == 0
    assert "promoted_object" in result.stdout
    assert "pixel_456" in result.stdout
    assert "COMPLETE_REGISTRATION" in result.stdout


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


def test_adsets_update_targeting_dry_run_json_does_not_build_client(monkeypatch):
    def fail_build_client(*_args):
        raise AssertionError("dry-run must not build an SDK client")

    monkeypatch.setattr("meta_cli.commands.adsets.build_client", fail_build_client)
    targeting = {"age_min": 25, "age_max": 45, "genders": [2]}
    result = runner.invoke(
        app,
        [
            "adsets",
            "update-targeting",
            "a1",
            "--targeting-json",
            json.dumps(targeting),
            "--yes",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["targeting"] == targeting


def test_adsets_update_targeting_from_adset_config(monkeypatch, tmp_path):
    path = tmp_path / "adset.yaml"
    path.write_text("name: Test\ntargeting:\n  age_min: 25\n  age_max: 45\n  genders: [2]\n")
    fake = FakeAdSetClient()
    monkeypatch.setattr("meta_cli.commands.adsets.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        ["adsets", "update-targeting", "a1", "--targeting-file", str(path), "--yes", "--json"],
    )

    assert result.exit_code == 0
    assert fake.last_targeting_update == {
        "adset_id": "a1",
        "targeting": {"age_min": 25, "age_max": 45, "genders": [2]},
    }


def test_adsets_update_targeting_requires_one_source():
    result = runner.invoke(app, ["adsets", "update-targeting", "a1", "--yes", "--json"])

    assert result.exit_code == 1
    assert "exactly one" in json.loads(result.stdout)["error"]


def test_adsets_pause_dry_run(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.adsets.build_client", lambda *_: FakeAdSetClient())
    result = runner.invoke(app, ["adsets", "pause", "a1", "--yes", "--dry-run", "--json"])
    assert result.exit_code == 0
    assert '"status": "PAUSED"' in result.stdout

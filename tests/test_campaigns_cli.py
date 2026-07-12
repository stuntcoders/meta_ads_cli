from __future__ import annotations

import json

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeClient:
    def __init__(self):
        self.last_list_kwargs = {}
        self.last_get_campaign = None
        self.last_create_payload = None

    def list_campaigns(
        self,
        fields,
        limit,
        after=None,
        before=None,
        auto_paginate=True,
        max_pages=None,
        include_paging=False,
    ):
        self.last_list_kwargs = {
            "after": after,
            "before": before,
            "auto_paginate": auto_paginate,
            "max_pages": max_pages,
            "limit": limit,
            "include_paging": include_paging,
        }
        assert "id" in fields
        data = [
            {
                "id": "1",
                "name": "Camp 1",
                "status": "PAUSED",
                "objective": "LINK_CLICKS",
                "daily_budget": "1000",
                "lifetime_budget": None,
            }
        ]
        if include_paging:
            return {"data": data, "paging": {"next_after": "cursor_next", "has_more": True}}
        return data

    def get_campaign_details(self, campaign_id, fields):
        self.last_get_campaign = {"campaign_id": campaign_id, "fields": fields}
        return {
            "id": campaign_id,
            "name": "Camp 1",
            "status": "PAUSED",
            "objective": "OUTCOME_LEADS",
        }

    def create_campaign(self, payload):
        self.last_create_payload = payload
        return {"id": "new_campaign"}

    def update_campaign_status(self, campaign_id, status):
        return {"id": campaign_id, "status": status}


def test_campaigns_list_json(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.campaigns.build_client", lambda *_: FakeClient())
    result = runner.invoke(app, ["campaigns", "list", "--json"])
    assert result.exit_code == 0
    assert '"id": "1"' in result.stdout
    assert '"paging"' in result.stdout
    assert '"next_after": "cursor_next"' in result.stdout


def test_campaigns_list_pagination_flags(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("meta_cli.commands.campaigns.build_client", lambda *_: fake)
    result = runner.invoke(
        app,
        [
            "campaigns",
            "list",
            "--after",
            "abc",
            "--no-paginate",
            "--max-pages",
            "2",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert fake.last_list_kwargs["after"] == "abc"
    assert fake.last_list_kwargs["auto_paginate"] is False
    assert fake.last_list_kwargs["max_pages"] == 2


def test_campaign_get_json(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("meta_cli.commands.campaigns.build_client", lambda *_: fake)
    result = runner.invoke(app, ["campaigns", "get", "123", "--json"])

    assert result.exit_code == 0
    assert '"id": "123"' in result.stdout
    assert fake.last_get_campaign is not None
    assert fake.last_get_campaign["campaign_id"] == "123"
    assert "created_time" in fake.last_get_campaign["fields"]


def test_campaign_create_dry_run_flags_is_json_and_does_not_build_client(monkeypatch):
    def fail_build_client(*_args):
        raise AssertionError("dry-run must not build an SDK client")

    monkeypatch.setattr("meta_cli.commands.campaigns.build_client", fail_build_client)
    result = runner.invoke(
        app,
        [
            "campaigns",
            "create",
            "--name",
            "Traffic Campaign",
            "--objective",
            "OUTCOME_TRAFFIC",
            "--special-ad-categories",
            "EMPLOYMENT,HOUSING",
            "--daily-budget",
            "1000",
            "--no-adset-budget-sharing",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["dry_run"] is True
    assert output["payload"] == {
        "name": "Traffic Campaign",
        "objective": "OUTCOME_TRAFFIC",
        "buying_type": "AUCTION",
        "special_ad_categories": ["EMPLOYMENT", "HOUSING"],
        "daily_budget": 1000,
        "is_adset_budget_sharing_enabled": False,
        "status": "PAUSED",
    }


def test_campaign_create_minimal_yaml(monkeypatch, tmp_path):
    config = tmp_path / "campaign.yaml"
    config.write_text('name: "YAML Campaign"\nobjective: "OUTCOME_LEADS"\n')
    fake = FakeClient()
    monkeypatch.setattr("meta_cli.commands.campaigns.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        ["campaigns", "create", "--config", str(config), "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["campaign"]["id"] == "new_campaign"
    assert fake.last_create_payload == {
        "name": "YAML Campaign",
        "objective": "OUTCOME_LEADS",
        "buying_type": "AUCTION",
        "special_ad_categories": [],
        "status": "PAUSED",
    }


def test_campaign_create_requires_name_and_objective():
    result = runner.invoke(app, ["campaigns", "create", "--name", "Incomplete", "--json"])

    assert result.exit_code == 1
    output = json.loads(result.stdout)
    assert output["ok"] is False
    assert "objective" in output["error"]


def test_campaign_pause_dry_run(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.campaigns.build_client", lambda *_: FakeClient())
    result = runner.invoke(app, ["campaigns", "pause", "123", "--yes", "--dry-run", "--json"])
    assert result.exit_code == 0
    assert '"dry_run": true' in result.stdout.lower()

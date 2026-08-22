from __future__ import annotations

import json

from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.commands.custom_audiences import _build_website_rule

runner = CliRunner()


class FakeCustomAudienceClient:
    def __init__(self):
        self.last_list_kwargs = None
        self.last_get = None
        self.last_create = None

    def list_custom_audiences(
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
            "fields": fields,
            "limit": limit,
            "after": after,
            "before": before,
            "auto_paginate": auto_paginate,
            "max_pages": max_pages,
            "include_paging": include_paging,
        }
        data = [
            {
                "id": "ca1",
                "name": "Web Visitors 30d",
                "subtype": "WEBSITE",
                "retention_days": 30,
                "approximate_count_lower_bound": 1000,
                "approximate_count_upper_bound": 5000,
            }
        ]
        if include_paging:
            return {"data": data, "paging": {"next_after": "next_ca"}}
        return data

    def get_custom_audience_details(self, custom_audience_id, fields):
        self.last_get = {"custom_audience_id": custom_audience_id, "fields": fields}
        return {
            "id": custom_audience_id,
            "name": "Web Visitors 30d",
            "subtype": "WEBSITE",
        }

    def create_custom_audience(self, payload):
        self.last_create = payload
        return {"id": "ca_new"}


def test_custom_audiences_list_json(monkeypatch):
    fake = FakeCustomAudienceClient()
    monkeypatch.setattr("meta_cli.commands.custom_audiences.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        ["custom-audiences", "list", "--before", "prev_ca", "--no-paginate", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"][0]["id"] == "ca1"
    assert payload["paging"]["next_after"] == "next_ca"
    assert fake.last_list_kwargs["before"] == "prev_ca"
    assert fake.last_list_kwargs["auto_paginate"] is False


def test_custom_audiences_list_table(monkeypatch):
    fake = FakeCustomAudienceClient()
    monkeypatch.setattr("meta_cli.commands.custom_audiences.build_client", lambda *_: fake)

    result = runner.invoke(app, ["custom-audiences", "list"])

    assert result.exit_code == 0
    assert "Web Visitors 30d" in result.stdout
    assert "1000-5000" in result.stdout


def test_custom_audiences_get_json(monkeypatch):
    fake = FakeCustomAudienceClient()
    monkeypatch.setattr("meta_cli.commands.custom_audiences.build_client", lambda *_: fake)

    result = runner.invoke(app, ["custom-audiences", "get", "ca1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["id"] == "ca1"
    assert fake.last_get["custom_audience_id"] == "ca1"
    assert "rule" in fake.last_get["fields"]


def test_custom_audiences_create_dry_run(monkeypatch):
    fake = FakeCustomAudienceClient()
    monkeypatch.setattr("meta_cli.commands.custom_audiences.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        [
            "custom-audiences",
            "create",
            "--name",
            "Leads 60d",
            "--pixel-id",
            "pixel1",
            "--event",
            "Lead",
            "--retention-days",
            "60",
            "--dry-run",
            "-y",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["payload"]["subtype"] == "WEBSITE"
    rule = json.loads(payload["payload"]["rule"])
    rule_entry = rule["inclusions"]["rules"][0]
    assert rule_entry["event_sources"] == [{"type": "pixel", "id": "pixel1"}]
    assert rule_entry["retention_seconds"] == 60 * 86400
    assert rule_entry["filter"]["filters"] == [
        {"field": "event", "operator": "eq", "value": "Lead"}
    ]
    assert fake.last_create is None


def test_custom_audiences_create_live(monkeypatch):
    fake = FakeCustomAudienceClient()
    monkeypatch.setattr("meta_cli.commands.custom_audiences.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        [
            "custom-audiences",
            "create",
            "--name",
            "Web Visitors 30d",
            "--pixel-id",
            "pixel1",
            "-y",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["custom_audience"]["id"] == "ca_new"
    rule = json.loads(fake.last_create["rule"])
    rule_entry = rule["inclusions"]["rules"][0]
    assert "filter" not in rule_entry
    assert rule_entry["retention_seconds"] == 30 * 86400


def test_custom_audiences_create_requires_pixel_id_without_rule_json(monkeypatch):
    fake = FakeCustomAudienceClient()
    monkeypatch.setattr("meta_cli.commands.custom_audiences.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        ["custom-audiences", "create", "--name", "No Pixel", "-y"],
    )

    assert result.exit_code != 0
    assert fake.last_create is None


def test_custom_audiences_create_rule_json_override(monkeypatch):
    fake = FakeCustomAudienceClient()
    monkeypatch.setattr("meta_cli.commands.custom_audiences.build_client", lambda *_: fake)

    custom_rule = {"inclusions": {"operator": "or", "rules": [{"raw": True}]}}
    result = runner.invoke(
        app,
        [
            "custom-audiences",
            "create",
            "--name",
            "Raw Rule",
            "--rule-json",
            json.dumps(custom_rule),
            "--dry-run",
            "-y",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert json.loads(payload["payload"]["rule"]) == custom_rule


def test_build_website_rule_with_url_contains():
    rule = _build_website_rule(
        pixel_id="p1", event="PageView", url_contains="tutor", retention_days=14
    )
    entry = rule["inclusions"]["rules"][0]
    assert entry["retention_seconds"] == 14 * 86400
    assert entry["filter"]["operator"] == "and"
    assert entry["filter"]["filters"] == [
        {"field": "event", "operator": "eq", "value": "PageView"},
        {"field": "url", "operator": "i_contains", "value": "tutor"},
    ]

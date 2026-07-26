from __future__ import annotations

import json

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeCustomConversionClient:
    def __init__(self):
        self.last_list_kwargs = None
        self.last_get = None
        self.last_create = None

    def list_custom_conversions(
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
                "id": "cc1",
                "name": "Student chat initiated",
                "custom_event_type": "CONTACT",
                "event_source_id": "pixel1",
                "rule": '{"event":{"eq":"Student chat initiated"}}',
            }
        ]
        if include_paging:
            return {"data": data, "paging": {"next_after": "next_cc"}}
        return data

    def get_custom_conversion_details(self, custom_conversion_id, fields):
        self.last_get = {"custom_conversion_id": custom_conversion_id, "fields": fields}
        return {
            "id": custom_conversion_id,
            "name": "Student chat initiated",
            "event_source_id": "pixel1",
        }

    def create_custom_conversion(self, payload):
        self.last_create = payload
        return {"id": "cc_new"}


def test_custom_conversions_list_json(monkeypatch):
    fake = FakeCustomConversionClient()
    monkeypatch.setattr("meta_cli.commands.custom_conversions.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        [
            "custom-conversions",
            "list",
            "--before",
            "prev_cc",
            "--no-paginate",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"][0]["id"] == "cc1"
    assert payload["paging"]["next_after"] == "next_cc"
    assert fake.last_list_kwargs["before"] == "prev_cc"
    assert fake.last_list_kwargs["auto_paginate"] is False


def test_custom_conversions_get_json(monkeypatch):
    fake = FakeCustomConversionClient()
    monkeypatch.setattr("meta_cli.commands.custom_conversions.build_client", lambda *_: fake)

    result = runner.invoke(app, ["custom-conversions", "get", "cc1", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["id"] == "cc1"
    assert fake.last_get["custom_conversion_id"] == "cc1"
    assert "last_fired_time" in fake.last_get["fields"]


def test_custom_conversions_create_dry_run_does_not_build_client(monkeypatch):
    def fail_build_client(*_args):
        raise AssertionError("dry-run must not build an SDK client")

    monkeypatch.setattr("meta_cli.commands.custom_conversions.build_client", fail_build_client)
    result = runner.invoke(
        app,
        [
            "custom-conversions",
            "create",
            "--name",
            "Student chat initiated",
            "--event-source-id",
            "pixel1",
            "--rule-json",
            '{"event":{"eq":"Student chat initiated"}}',
            "--custom-event-type",
            "contact",
            "--action-source-type",
            "website",
            "--yes",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)["payload"]
    assert payload == {
        "name": "Student chat initiated",
        "event_source_id": "pixel1",
        "rule": '{"event":{"eq":"Student chat initiated"}}',
        "custom_event_type": "CONTACT",
        "action_source_type": "website",
    }


def test_custom_conversions_create_calls_sdk(monkeypatch):
    fake = FakeCustomConversionClient()
    monkeypatch.setattr("meta_cli.commands.custom_conversions.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        [
            "custom-conversions",
            "create",
            "--name",
            "Student chat initiated",
            "--event-source-id",
            "pixel1",
            "--rule-json",
            '{"event":{"eq":"Student chat initiated"}}',
            "--custom-event-type",
            "CONTACT",
            "--yes",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["custom_conversion"]["id"] == "cc_new"
    assert fake.last_create["event_source_id"] == "pixel1"
    assert fake.last_create["custom_event_type"] == "CONTACT"


def test_custom_conversions_create_rejects_non_object_rule():
    result = runner.invoke(
        app,
        [
            "custom-conversions",
            "create",
            "--name",
            "Bad",
            "--event-source-id",
            "pixel1",
            "--rule-json",
            "[]",
            "--yes",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert "non-empty JSON object" in json.loads(result.stdout)["error"]

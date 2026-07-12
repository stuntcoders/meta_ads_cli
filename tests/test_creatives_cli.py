from __future__ import annotations

import json

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeClient:
    def __init__(self):
        self.last_get = None

    def get_creative_details(self, creative_id, fields):
        self.last_get = {"creative_id": creative_id, "fields": fields}
        return {
            "id": creative_id,
            "name": "Creative",
            "object_story_spec": {
                "page_id": "page_1",
                "instagram_actor_id": "instagram_1",
            },
        }


def test_creative_get_json(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("meta_cli.commands.creatives.build_client", lambda *_: fake)

    result = runner.invoke(app, ["creatives", "get", "creative_1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["object_story_spec"]["instagram_actor_id"] == "instagram_1"
    assert fake.last_get["creative_id"] == "creative_1"
    assert "asset_feed_spec" in fake.last_get["fields"]


def test_creative_get_table(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.creatives.build_client", lambda *_: FakeClient())

    result = runner.invoke(app, ["creatives", "get", "creative_1"])

    assert result.exit_code == 0
    assert "Creative creative_1" in result.stdout
    assert "object_story_spec" in result.stdout

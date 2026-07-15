from __future__ import annotations

import json

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeClient:
    def __init__(self):
        self.last_get = None
        self.creative_payload = None

    def create_creative(self, payload):
        self.creative_payload = payload
        return {"id": "creative_1", **payload}

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


def test_creative_create_dry_run(tmp_path):
    config = tmp_path / "ad.yaml"
    config.write_text(
        "\n".join(
            [
                "adset_id: adset_1",
                "name: Test Ad",
                "page_id: page_1",
                "destination_url: https://example.com",
                "headlines:",
                "- Test headline",
                "bodies:",
                "- Test body",
                "image_hashes:",
                "- image_hash_1",
            ]
        )
    )

    result = runner.invoke(app, ["creatives", "create", "--config", str(config), "--dry-run", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["creative_payload"]["object_story_spec"]["link_data"]["image_hash"] == "image_hash_1"


def test_creative_create_calls_sdk(tmp_path, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("meta_cli.commands.creatives.build_client", lambda *_: fake)
    config = tmp_path / "ad.yaml"
    config.write_text(
        "\n".join(
            [
                "adset_id: adset_1",
                "name: Test Ad",
                "page_id: page_1",
                "destination_url: https://example.com",
                "headlines:",
                "- Test headline",
                "bodies:",
                "- Test body",
                "image_hashes:",
                "- image_hash_1",
            ]
        )
    )

    result = runner.invoke(app, ["creatives", "create", "--config", str(config), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["creative"]["id"] == "creative_1"
    assert fake.creative_payload["object_story_spec"]["link_data"]["image_hash"] == "image_hash_1"


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

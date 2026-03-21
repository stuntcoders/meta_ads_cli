from __future__ import annotations

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeAdsClient:
    def __init__(self):
        self.creative_payload = None
        self.ad_payload = None

    def list_all_ads(self, fields, limit):
        return [{"id": "1", "name": "Ad", "status": "PAUSED", "effective_status": "PAUSED"}]

    def list_ads(self, adset_id, fields, limit):
        return [{"id": "2", "name": "Ad2", "status": "ACTIVE", "adset_id": adset_id}]

    def create_creative(self, payload):
        self.creative_payload = payload
        return {"id": "creative_1", **payload}

    def create_ad(self, payload):
        self.ad_payload = payload
        return {"id": "ad_1", **payload}

    def update_ad_status(self, ad_id, status):
        return {"id": ad_id, "status": status}


def test_ads_list_requires_scope():
    result = runner.invoke(app, ["ads", "list", "--json"])
    assert result.exit_code == 1
    assert "Provide --all or --adset-id" in result.stdout


def test_ads_list_all_json(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda *_: FakeAdsClient())
    result = runner.invoke(app, ["ads", "list", "--all", "--json"])
    assert result.exit_code == 0
    assert '"id": "1"' in result.stdout


def test_ads_create_dry_run_multi_text(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda *_: FakeAdsClient())
    result = runner.invoke(
        app,
        [
            "ads",
            "create",
            "--adset-id",
            "a1",
            "--name",
            "Test Ad",
            "--page-id",
            "p1",
            "--destination-url",
            "https://example.com",
            "--headlines",
            "h1,h2",
            "--bodies",
            "b1,b2",
            "--image-hashes",
            "im1,im2",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert '"uses_asset_feed_spec": true' in result.stdout.lower()


def test_ads_create_non_dry_run_calls_creative_and_ad(monkeypatch):
    fake = FakeAdsClient()
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda *_: fake)
    result = runner.invoke(
        app,
        [
            "ads",
            "create",
            "--adset-id",
            "a1",
            "--name",
            "Test Ad",
            "--page-id",
            "p1",
            "--destination-url",
            "https://example.com",
            "--headlines",
            "h1",
            "--bodies",
            "b1",
            "--image-hashes",
            "im1",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert fake.creative_payload is not None
    assert fake.ad_payload["creative"]["creative_id"] == "creative_1"


def test_ads_pause_dry_run(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda *_: FakeAdsClient())
    result = runner.invoke(app, ["ads", "pause", "a1", "--yes", "--dry-run", "--json"])
    assert result.exit_code == 0
    assert '"status": "PAUSED"' in result.stdout

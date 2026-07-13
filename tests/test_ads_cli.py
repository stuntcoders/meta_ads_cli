from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_environments_file(monkeypatch, tmp_path):
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(tmp_path / "environments.yaml"))


def write_active_environment(path, *, page_id="profile_page", instagram_id="profile_ig"):
    path.write_text(
        f"""
active_profile: sandbox
profiles:
  sandbox:
    access_token: test-token
    app_id: test-app
    app_secret: test-secret
    ad_account_id: 123456
    facebook_page_id: {page_id}
    instagram_user_id: {instagram_id}
""".strip()
    )


class FakeAdsClient:
    def __init__(self):
        self.creative_payload = None
        self.ad_payload = None
        self.last_list_kwargs = {}
        self.last_get_ad = None

    def list_all_ads(
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
        data = [{"id": "1", "name": "Ad", "status": "PAUSED", "effective_status": "PAUSED"}]
        if include_paging:
            return {"data": data, "paging": {"next_after": "ads_next"}}
        return data

    def list_ads(
        self,
        adset_id,
        fields,
        limit,
        after=None,
        before=None,
        auto_paginate=True,
        max_pages=None,
        include_paging=False,
    ):
        self.last_list_kwargs = {
            "adset_id": adset_id,
            "after": after,
            "before": before,
            "auto_paginate": auto_paginate,
            "max_pages": max_pages,
            "limit": limit,
            "include_paging": include_paging,
        }
        data = [{"id": "2", "name": "Ad2", "status": "ACTIVE", "adset_id": adset_id}]
        if include_paging:
            return {"data": data, "paging": {"next_after": "ads_next"}}
        return data

    def get_ad_details(self, ad_id, fields):
        self.last_get_ad = {"ad_id": ad_id, "fields": fields}
        return {
            "id": ad_id,
            "name": "Ad",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "adset_id": "adset_1",
            "campaign_id": "campaign_1",
        }

    def create_creative(self, payload):
        self.creative_payload = payload
        return {"id": "creative_1", **payload}

    def create_ad(self, payload):
        self.ad_payload = payload
        return {"id": "ad_1", **payload}

    def update_ad_status(self, ad_id, status):
        return {"id": ad_id, "status": status}

    def update_ad_creative(self, ad_id, creative_id):
        return {"id": ad_id, "creative": {"creative_id": creative_id}}


def test_ads_list_requires_scope():
    result = runner.invoke(app, ["ads", "list", "--json"])
    assert result.exit_code == 1
    assert "Provide --all or --adset-id" in result.stdout


def test_ads_list_all_json(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda *_: FakeAdsClient())
    result = runner.invoke(app, ["ads", "list", "--all", "--json"])
    assert result.exit_code == 0
    assert '"id": "1"' in result.stdout
    assert '"paging"' in result.stdout
    assert '"next_after": "ads_next"' in result.stdout


def test_ads_list_passes_pagination_flags(monkeypatch):
    fake = FakeAdsClient()
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda *_: fake)
    result = runner.invoke(
        app,
        ["ads", "list", "--all", "--after", "c2", "--max-pages", "2", "--no-paginate", "--json"],
    )
    assert result.exit_code == 0
    assert fake.last_list_kwargs["after"] == "c2"
    assert fake.last_list_kwargs["auto_paginate"] is False
    assert fake.last_list_kwargs["max_pages"] == 2


def test_ads_get_json(monkeypatch):
    fake = FakeAdsClient()
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda *_: fake)
    result = runner.invoke(app, ["ads", "get", "ad_1", "--json"])

    assert result.exit_code == 0
    assert '"id": "ad_1"' in result.stdout
    assert fake.last_get_ad is not None
    assert fake.last_get_ad["ad_id"] == "ad_1"
    assert "tracking_specs" in fake.last_get_ad["fields"]
    assert "issues_info" in fake.last_get_ad["fields"]
    assert "failed_delivery_checks" in fake.last_get_ad["fields"]


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
            "--instagram-user-id",
            "ig1",
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
    payload = json.loads(result.stdout)
    assert payload["uses_asset_feed_spec"] is True
    assert payload["creative_payload"]["object_story_spec"]["instagram_user_id"] == "ig1"


def test_ads_create_uses_profile_identity_defaults_and_stays_paused(tmp_path, monkeypatch):
    environments = tmp_path / "profiles.yaml"
    write_active_environment(environments)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(environments))
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
            "Profile Ad",
            "--destination-url",
            "https://example.com",
            "--bodies",
            "Body",
            "--image-hashes",
            "image1",
            "--json",
        ],
    )

    assert result.exit_code == 0
    story = fake.creative_payload["object_story_spec"]
    assert story["page_id"] == "profile_page"
    assert story["instagram_user_id"] == "profile_ig"
    assert fake.ad_payload["status"] == "PAUSED"


def test_ads_create_explicit_identity_overrides_profile(tmp_path, monkeypatch):
    environments = tmp_path / "profiles.yaml"
    write_active_environment(environments)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(environments))

    result = runner.invoke(
        app,
        [
            "ads",
            "create",
            "--adset-id",
            "a1",
            "--name",
            "Explicit Ad",
            "--page-id",
            "explicit_page",
            "--instagram-user-id",
            "explicit_ig",
            "--destination-url",
            "https://example.com",
            "--bodies",
            "Body",
            "--image-hashes",
            "image1",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0
    story = json.loads(result.stdout)["creative_payload"]["object_story_spec"]
    assert story["page_id"] == "explicit_page"
    assert story["instagram_user_id"] == "explicit_ig"


def test_ads_create_yaml_identity_overrides_profile(tmp_path, monkeypatch):
    environments = tmp_path / "profiles.yaml"
    write_active_environment(environments)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(environments))
    config = tmp_path / "ad.yaml"
    config.write_text(
        """
adset_id: a1
name: YAML Ad
page_id: yaml_page
instagram_actor_id: yaml_actor
destination_url: https://example.com
bodies: [Body]
image_hashes: [image1]
""".strip()
    )

    result = runner.invoke(
        app, ["ads", "create", "--config", str(config), "--dry-run", "--json"]
    )

    assert result.exit_code == 0
    story = json.loads(result.stdout)["creative_payload"]["object_story_spec"]
    assert story["page_id"] == "yaml_page"
    assert story["instagram_actor_id"] == "yaml_actor"
    assert "instagram_user_id" not in story


def test_ads_create_legacy_auth_override_does_not_use_profile_defaults(tmp_path, monkeypatch):
    environments = tmp_path / "profiles.yaml"
    write_active_environment(environments)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(environments))

    result = runner.invoke(
        app,
        [
            "ads",
            "create",
            "--adset-id",
            "a1",
            "--name",
            "Legacy Override",
            "--destination-url",
            "https://example.com",
            "--bodies",
            "Body",
            "--image-hashes",
            "image1",
            "--auth-config",
            str(tmp_path / "legacy-auth.yaml"),
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert "page_id is required unless existing_creative_id is provided" in json.loads(
        result.stdout
    )["error"]


def test_ads_create_without_explicit_or_profile_page_keeps_validation_error():
    result = runner.invoke(
        app,
        [
            "ads",
            "create",
            "--adset-id",
            "a1",
            "--name",
            "Missing Page",
            "--destination-url",
            "https://example.com",
            "--bodies",
            "Body",
            "--image-hashes",
            "image1",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert "page_id is required unless existing_creative_id is provided" in json.loads(
        result.stdout
    )["error"]


def test_ads_create_placement_images_from_json_flags_dry_run():
    image_assets = [
        {"hash": "portrait", "label": "feed_4x5"},
        {"hash": "square", "label": "feed_1x1"},
        {"hash": "story", "label": "story_9x16"},
    ]
    rules = [
        {
            "customization_spec": {
                "publisher_platforms": ["facebook", "instagram"],
                "facebook_positions": ["feed"],
                "instagram_positions": ["stream"],
            },
            "image_label": "feed_4x5",
            "priority": 1,
        },
        {
            "customization_spec": {
                "publisher_platforms": ["facebook", "instagram"],
                "facebook_positions": ["story"],
                "instagram_positions": ["story"],
            },
            "image_label": "story_9x16",
            "priority": 2,
        },
    ]
    result = runner.invoke(
        app,
        [
            "ads",
            "create",
            "--adset-id",
            "a1",
            "--name",
            "Placement Ad",
            "--page-id",
            "p1",
            "--destination-url",
            "https://example.com",
            "--bodies",
            "Body",
            "--image-assets-json",
            json.dumps(image_assets),
            "--asset-customization-rules-json",
            json.dumps(rules),
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0
    output = json.loads(result.stdout)
    feed = output["creative_payload"]["asset_feed_spec"]
    assert feed["images"][0]["adlabels"] == [{"name": "feed_4x5"}]
    assert feed["asset_customization_rules"][1]["image_label"] == {"name": "story_9x16"}


def test_ads_create_placement_yaml_matches_json_structure(tmp_path):
    path = tmp_path / "placement-ad.yaml"
    path.write_text(
        """
adset_id: a1
name: Placement Ad
page_id: p1
destination_url: https://example.com
bodies: [Body]
image_assets:
  - {hash: portrait, label: feed_4x5}
  - {hash: square, label: feed_1x1}
  - {hash: story, label: story_9x16}
asset_customization_rules:
  - customization_spec:
      publisher_platforms: [facebook, instagram]
      facebook_positions: [feed]
      instagram_positions: [stream]
    image_label: feed_4x5
    priority: 1
""".strip()
    )

    result = runner.invoke(
        app, ["ads", "create", "--config", str(path), "--dry-run", "--json"]
    )

    assert result.exit_code == 0
    feed = json.loads(result.stdout)["creative_payload"]["asset_feed_spec"]
    assert [image["hash"] for image in feed["images"]] == ["portrait", "square", "story"]
    assert feed["asset_customization_rules"][0]["priority"] == 1


def test_ads_create_rejects_mixed_legacy_and_placement_images():
    result = runner.invoke(
        app,
        [
            "ads",
            "create",
            "--adset-id",
            "a1",
            "--name",
            "Ad",
            "--page-id",
            "p1",
            "--destination-url",
            "https://example.com",
            "--bodies",
            "Body",
            "--image-hashes",
            "legacy",
            "--image-assets-json",
            '[{"hash":"portrait","label":"feed"}]',
            "--asset-customization-rules-json",
            '[{"customization_spec":{"publisher_platforms":["facebook"]},"image_label":"feed"}]',
            "--dry-run",
        ],
    )

    assert result.exit_code == 1
    assert "either image_hashes or image_assets" in result.stdout


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


def test_ads_update_creative_dry_run(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda *_: FakeAdsClient())
    result = runner.invoke(
        app,
        [
            "ads",
            "update-creative",
            "a1",
            "--creative-id",
            "c2",
            "--yes",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert '"ad_id": "a1"' in result.stdout
    assert '"creative_id": "c2"' in result.stdout


def test_ads_update_creative_calls_sdk(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda *_: FakeAdsClient())
    result = runner.invoke(
        app,
        ["ads", "update-creative", "a1", "--creative-id", "c2", "--yes", "--json"],
    )
    assert result.exit_code == 0
    assert '"ok": true' in result.stdout.lower()
    assert '"creative_id": "c2"' in result.stdout


def test_ads_pause_dry_run(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda *_: FakeAdsClient())
    result = runner.invoke(app, ["ads", "pause", "a1", "--yes", "--dry-run", "--json"])
    assert result.exit_code == 0
    assert '"status": "PAUSED"' in result.stdout

from __future__ import annotations

import pytest

from meta_cli.schemas import (
    AdCreateConfig,
    AdSetCreateConfig,
    CampaignCreateConfig,
    load_yaml_model,
)


def test_campaign_minimal_config_uses_safe_defaults():
    cfg = CampaignCreateConfig(name="Campaign", objective="OUTCOME_TRAFFIC")

    assert cfg.to_payload() == {
        "name": "Campaign",
        "objective": "OUTCOME_TRAFFIC",
        "buying_type": "AUCTION",
        "special_ad_categories": [],
        "status": "PAUSED",
    }


def test_campaign_requires_name_and_objective():
    with pytest.raises(ValueError):
        CampaignCreateConfig.model_validate({})


def test_campaign_to_payload_supports_optional_budgets():
    cfg = CampaignCreateConfig(
        name="Campaign",
        objective="OUTCOME_TRAFFIC",
        daily_budget=1000,
    )

    assert cfg.to_payload()["daily_budget"] == 1000
    assert "lifetime_budget" not in cfg.to_payload()


def test_adset_requires_budget():
    with pytest.raises(ValueError):
        AdSetCreateConfig(campaign_id="123", name="Test")


def test_adset_to_payload_excludes_none():
    cfg = AdSetCreateConfig(
        campaign_id="123",
        name="Adset",
        daily_budget=1000,
        targeting={"geo_locations": {"countries": ["US"]}},
    )
    payload = cfg.to_payload()
    assert payload["campaign_id"] == "123"
    assert "lifetime_budget" not in payload


def test_adcreate_asset_feed_payload_for_multi_text():
    cfg = AdCreateConfig(
        adset_id="adset_1",
        name="Ad",
        page_id="page_1",
        destination_url="https://example.com",
        headlines=["H1", "H2"],
        bodies=["B1", "B2"],
        descriptions=["D1"],
        image_hashes=["img1", "img2"],
    )
    payload = cfg.build_creative_payload()
    assert cfg.uses_asset_feed_spec() is True
    assert "asset_feed_spec" in payload
    assert len(payload["asset_feed_spec"]["titles"]) == 2


def _placement_ad_config(**overrides):
    values = {
        "adset_id": "adset_1",
        "name": "Placement Ad",
        "page_id": "page_1",
        "destination_url": "https://example.com",
        "bodies": ["Body"],
        "image_assets": [
            {"hash": "portrait", "label": "feed_4x5"},
            {"hash": "square", "label": "feed_1x1"},
            {"hash": "story", "label": "story_9x16"},
        ],
        "asset_customization_rules": [
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
        ],
    }
    values.update(overrides)
    return AdCreateConfig(**values)


def test_adcreate_placement_images_build_labeled_asset_feed_payload():
    payload = _placement_ad_config().build_creative_payload()
    feed = payload["asset_feed_spec"]

    assert feed["images"] == [
        {"hash": "portrait", "adlabels": [{"name": "feed_4x5"}]},
        {"hash": "square", "adlabels": [{"name": "feed_1x1"}]},
        {"hash": "story", "adlabels": [{"name": "story_9x16"}]},
    ]
    assert feed["asset_customization_rules"][0] == {
        "customization_spec": {
            "publisher_platforms": ["facebook", "instagram"],
            "facebook_positions": ["feed"],
            "instagram_positions": ["stream"],
        },
        "priority": 1,
        "image_label": {"name": "feed_4x5"},
    }
    assert feed["ad_formats"] == ["SINGLE_IMAGE"]


def test_adcreate_legacy_single_image_payload_is_unchanged():
    cfg = AdCreateConfig(
        adset_id="adset_1",
        name="Ad",
        page_id="page_1",
        destination_url="https://example.com",
        headlines=["Headline"],
        bodies=["Body"],
        image_hashes=["legacy_hash"],
    )

    assert cfg.uses_asset_feed_spec() is False
    assert cfg.build_creative_payload()["object_story_spec"]["link_data"]["image_hash"] == (
        "legacy_hash"
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"image_hashes": ["legacy"]}, "either image_hashes or image_assets"),
        (
            {
                "image_assets": [{"hash": "portrait", "label": " "}],
                "asset_customization_rules": [],
            },
            "label must not be blank",
        ),
        (
            {
                "image_assets": [
                    {"hash": "one", "label": "same"},
                    {"hash": "two", "label": "same"},
                ]
            },
            "labels must be unique",
        ),
        (
            {
                "asset_customization_rules": [
                    {
                        "customization_spec": {"publisher_platforms": ["facebook"]},
                        "image_label": "unknown",
                    }
                ]
            },
            "references unknown label",
        ),
        ({"asset_customization_rules": []}, "asset_customization_rule is required"),
    ],
)
def test_adcreate_rejects_invalid_placement_image_config(overrides, message):
    with pytest.raises(ValueError, match=message):
        _placement_ad_config(**overrides)


def test_adcreate_requires_images_when_customization_rules_are_provided():
    with pytest.raises(ValueError, match="image_assets is required"):
        AdCreateConfig(
            adset_id="adset_1",
            name="Ad",
            page_id="page_1",
            destination_url="https://example.com",
            bodies=["Body"],
            asset_customization_rules=[
                {
                    "customization_spec": {"publisher_platforms": ["facebook"]},
                    "image_label": "feed",
                }
            ],
        )


def test_adcreate_build_ad_payload_uses_creative_id():
    cfg = AdCreateConfig(
        adset_id="adset_1",
        name="Ad",
        existing_creative_id="123",
    )
    payload = cfg.build_ad_payload("123")
    assert payload["creative"]["creative_id"] == "123"
    assert payload["status"] == "PAUSED"


def test_adcreate_rejects_image_and_video_combo():
    with pytest.raises(ValueError):
        AdCreateConfig(
            adset_id="adset_1",
            name="Ad",
            page_id="page_1",
            destination_url="https://example.com",
            bodies=["Body"],
            image_hashes=["hash1"],
            video_id="video1",
        )


def test_load_yaml_ad_with_placement_images(tmp_path):
    path = tmp_path / "ad.yaml"
    path.write_text(
        """
adset_id: adset_1
name: Placement Ad
page_id: page_1
destination_url: https://example.com
bodies: [Body]
image_assets:
  - hash: portrait_hash
    label: feed_4x5
asset_customization_rules:
  - customization_spec:
      publisher_platforms: [facebook, instagram]
      facebook_positions: [feed]
      instagram_positions: [stream]
    image_label: feed_4x5
    priority: 1
""".strip()
    )

    cfg = load_yaml_model(str(path), AdCreateConfig)
    assert cfg.image_assets[0].label == "feed_4x5"
    assert cfg.asset_customization_rules[0].priority == 1


def test_load_yaml_model(tmp_path):
    path = tmp_path / "adset.yaml"
    path.write_text(
        """
campaign_id: "123"
name: "Test"
daily_budget: 1000
targeting:
  geo_locations:
    countries: ["US"]
""".strip()
    )
    cfg = load_yaml_model(str(path), AdSetCreateConfig)
    assert cfg.campaign_id == "123"

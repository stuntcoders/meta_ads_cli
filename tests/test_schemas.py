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


def test_campaign_supports_adset_budget_sharing_flag():
    cfg = CampaignCreateConfig(
        name="Campaign",
        objective="OUTCOME_LEADS",
        is_adset_budget_sharing_enabled=False,
    )

    assert cfg.to_payload()["is_adset_budget_sharing_enabled"] is False


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


def test_adcreate_dynamic_multi_copy_payload_without_customization_is_unchanged():
    cfg = AdCreateConfig(
        adset_id="adset_1",
        name="Ad",
        page_id="page_1",
        destination_url="https://example.com",
        headlines=["H1", "H2"],
        bodies=["B1", "B2"],
        descriptions=["D1", "D2"],
        image_hashes=["img1", "img2"],
    )

    assert cfg.uses_asset_feed_spec() is True
    assert cfg.build_creative_payload() == {
        "name": "Ad - creative",
        "object_story_spec": {"page_id": "page_1"},
        "asset_feed_spec": {
            "bodies": [{"text": "B1"}, {"text": "B2"}],
            "titles": [{"text": "H1"}, {"text": "H2"}],
            "link_urls": [{"website_url": "https://example.com"}],
            "descriptions": [{"text": "D1"}, {"text": "D2"}],
            "images": [{"hash": "img1"}, {"hash": "img2"}],
            "ad_formats": ["SINGLE_IMAGE"],
            "call_to_action_types": ["LEARN_MORE"],
        },
    }


def test_adcreate_parses_labeled_text_assets_and_rule_references():
    cfg = AdCreateConfig.model_validate(
        {
            "adset_id": "adset_1",
            "name": "Placement Copy Ad",
            "page_id": "page_1",
            "destination_url": "https://example.com",
            "headline_assets": [{"text": "Feed headline", "label": " headline_feed "}],
            "body_assets": [{"text": "Feed body", "label": "body_feed"}],
            "description_assets": [
                {"text": "Feed description", "label": "description_feed"}
            ],
            "image_assets": [{"hash": "portrait", "label": "feed_4x5"}],
            "asset_customization_rules": [
                {
                    "customization_spec": {"publisher_platforms": ["facebook"]},
                    "image_label": "feed_4x5",
                    "title_label": "headline_feed",
                    "body_label": "body_feed",
                    "description_label": "description_feed",
                }
            ],
        }
    )

    assert [(asset.text, asset.label) for asset in cfg.headline_assets] == [
        ("Feed headline", "headline_feed")
    ]
    assert [(asset.text, asset.label) for asset in cfg.body_assets] == [
        ("Feed body", "body_feed")
    ]
    assert [(asset.text, asset.label) for asset in cfg.description_assets] == [
        ("Feed description", "description_feed")
    ]
    rule = cfg.asset_customization_rules[0]
    assert (rule.title_label, rule.body_label, rule.description_label) == (
        "headline_feed",
        "body_feed",
        "description_feed",
    )


def test_adcreate_legacy_text_lists_still_parse_unchanged():
    cfg = AdCreateConfig.model_validate(
        {
            "adset_id": "adset_1",
            "name": "Legacy Copy Ad",
            "page_id": "page_1",
            "destination_url": "https://example.com",
            "headlines": ["Headline one", "Headline two"],
            "bodies": ["Body one", "Body two"],
            "descriptions": ["Description one", "Description two"],
            "image_hashes": ["image_hash"],
        }
    )

    assert cfg.headlines == ["Headline one", "Headline two"]
    assert cfg.bodies == ["Body one", "Body two"]
    assert cfg.descriptions == ["Description one", "Description two"]
    assert cfg.headline_assets == []
    assert cfg.body_assets == []
    assert cfg.description_assets == []


@pytest.mark.parametrize(
    ("legacy_field", "asset_field", "legacy_value", "asset_value"),
    [
        ("headlines", "headline_assets", ["Headline"], [{"text": "Headline", "label": "h1"}]),
        ("bodies", "body_assets", ["Body"], [{"text": "Body", "label": "b1"}]),
        (
            "descriptions",
            "description_assets",
            ["Description"],
            [{"text": "Description", "label": "d1"}],
        ),
    ],
)
def test_adcreate_rejects_mixed_legacy_and_labeled_text(
    legacy_field, asset_field, legacy_value, asset_value
):
    values = {
        "adset_id": "adset_1",
        "name": "Mixed Copy Ad",
        "page_id": "page_1",
        "destination_url": "https://example.com",
        "body_assets": [{"text": "Default body", "label": "default_body"}],
        "image_hashes": ["image_hash"],
        legacy_field: legacy_value,
        asset_field: asset_value,
    }

    with pytest.raises(
        ValueError, match=f"Provide either {legacy_field} or {asset_field}, not both"
    ):
        AdCreateConfig.model_validate(values)


@pytest.mark.parametrize("asset_field", ["headline_assets", "body_assets", "description_assets"])
def test_adcreate_rejects_blank_text_asset_labels(asset_field):
    values = {
        "adset_id": "adset_1",
        "name": "Blank Label Ad",
        "page_id": "page_1",
        "destination_url": "https://example.com",
        "body_assets": [{"text": "Default body", "label": "default_body"}],
        "image_hashes": ["image_hash"],
    }
    values[asset_field] = [{"text": "Copy", "label": " "}]

    with pytest.raises(ValueError, match="Text asset label must not be blank"):
        AdCreateConfig.model_validate(values)


@pytest.mark.parametrize("asset_field", ["headline_assets", "body_assets", "description_assets"])
def test_adcreate_rejects_duplicate_text_asset_labels(asset_field):
    values = {
        "adset_id": "adset_1",
        "name": "Duplicate Label Ad",
        "page_id": "page_1",
        "destination_url": "https://example.com",
        "body_assets": [{"text": "Default body", "label": "default_body"}],
        "image_hashes": ["image_hash"],
    }
    values[asset_field] = [
        {"text": "Copy one", "label": "duplicate"},
        {"text": "Copy two", "label": "duplicate"},
    ]

    with pytest.raises(ValueError, match=f"{asset_field} labels must be unique"):
        AdCreateConfig.model_validate(values)


@pytest.mark.parametrize("rule_field", ["title_label", "body_label", "description_label"])
def test_adcreate_rejects_blank_customization_rule_text_labels(rule_field):
    values = {
        "adset_id": "adset_1",
        "name": "Blank Rule Label Ad",
        "page_id": "page_1",
        "destination_url": "https://example.com",
        "bodies": ["Body"],
        "image_assets": [{"hash": "portrait", "label": "feed_4x5"}],
        "asset_customization_rules": [
            {
                "customization_spec": {"publisher_platforms": ["facebook"]},
                "image_label": "feed_4x5",
                rule_field: " ",
            }
        ],
    }

    with pytest.raises(ValueError, match="Customization rule text label must not be blank"):
        AdCreateConfig.model_validate(values)


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


def test_adcreate_labeled_text_and_rule_selectors_serialize_exactly():
    cfg = AdCreateConfig(
        adset_id="adset_1",
        name="Placement Copy Ad",
        page_id="page_1",
        destination_url="https://example.com",
        headline_assets=[
            {"text": "Feed headline", "label": "headline_feed"},
            {"text": "Story headline", "label": "headline_story"},
        ],
        body_assets=[
            {"text": "Feed body", "label": "body_feed"},
            {"text": "Story body", "label": "body_story"},
        ],
        description_assets=[
            {"text": "Feed description", "label": "description_feed"},
            {"text": "Story description", "label": "description_story"},
        ],
        image_assets=[
            {"hash": "portrait", "label": "image_feed"},
            {"hash": "story", "label": "image_story"},
        ],
        asset_customization_rules=[
            {
                "customization_spec": {
                    "publisher_platforms": ["facebook", "instagram"],
                    "facebook_positions": ["feed"],
                    "instagram_positions": ["stream"],
                },
                "image_label": "image_feed",
                "title_label": "headline_feed",
                "body_label": "body_feed",
                "description_label": "description_feed",
                "priority": 1,
            },
            {
                "customization_spec": {
                    "publisher_platforms": ["facebook", "instagram"],
                    "facebook_positions": ["story"],
                    "instagram_positions": ["story"],
                },
                "image_label": "image_story",
                "title_label": "headline_story",
                "body_label": "body_story",
                "description_label": "description_story",
                "priority": 2,
            },
        ],
    )

    assert cfg.build_creative_payload()["asset_feed_spec"] == {
        "bodies": [
            {"text": "Feed body", "adlabels": [{"name": "body_feed"}]},
            {"text": "Story body", "adlabels": [{"name": "body_story"}]},
        ],
        "titles": [
            {"text": "Feed headline", "adlabels": [{"name": "headline_feed"}]},
            {"text": "Story headline", "adlabels": [{"name": "headline_story"}]},
        ],
        "link_urls": [{"website_url": "https://example.com"}],
        "descriptions": [
            {
                "text": "Feed description",
                "adlabels": [{"name": "description_feed"}],
            },
            {
                "text": "Story description",
                "adlabels": [{"name": "description_story"}],
            },
        ],
        "images": [
            {"hash": "portrait", "adlabels": [{"name": "image_feed"}]},
            {"hash": "story", "adlabels": [{"name": "image_story"}]},
        ],
        "asset_customization_rules": [
            {
                "customization_spec": {
                    "publisher_platforms": ["facebook", "instagram"],
                    "facebook_positions": ["feed"],
                    "instagram_positions": ["stream"],
                },
                "priority": 1,
                "image_label": {"name": "image_feed"},
                "title_label": {"name": "headline_feed"},
                "body_label": {"name": "body_feed"},
                "description_label": {"name": "description_feed"},
            },
            {
                "customization_spec": {
                    "publisher_platforms": ["facebook", "instagram"],
                    "facebook_positions": ["story"],
                    "instagram_positions": ["story"],
                },
                "priority": 2,
                "image_label": {"name": "image_story"},
                "title_label": {"name": "headline_story"},
                "body_label": {"name": "body_story"},
                "description_label": {"name": "description_story"},
            },
        ],
        "ad_formats": ["SINGLE_IMAGE"],
        "call_to_action_types": ["LEARN_MORE"],
    }


@pytest.mark.parametrize(
    ("asset_field", "rule_field", "text_type"),
    [
        ("headline_assets", "title_label", "headline"),
        ("body_assets", "body_label", "body"),
        ("description_assets", "description_label", "description"),
    ],
)
def test_adcreate_rejects_unknown_text_rule_references(
    asset_field, rule_field, text_type
):
    values = {
        "adset_id": "adset_1",
        "name": "Unknown Copy Label Ad",
        "page_id": "page_1",
        "destination_url": "https://example.com",
        "bodies": ["Body"],
        "image_assets": [{"hash": "portrait", "label": "image_feed"}],
        "asset_customization_rules": [
            {
                "customization_spec": {"publisher_platforms": ["facebook"]},
                "image_label": "image_feed",
                rule_field: "unknown_copy",
            }
        ],
        asset_field: [{"text": "Known copy", "label": "known_copy"}],
    }
    if asset_field == "body_assets":
        values["bodies"] = []

    with pytest.raises(
        ValueError,
        match=(
            f"Customization rule {rule_field} references unknown "
            f"{text_type} asset label.*unknown_copy"
        ),
    ):
        AdCreateConfig.model_validate(values)


@pytest.mark.parametrize(
    ("asset_field", "rule_field"),
    [
        ("headline_assets", "title_label"),
        ("body_assets", "body_label"),
        ("description_assets", "description_label"),
    ],
)
def test_adcreate_requires_selector_on_every_rule_for_multiple_labeled_text_assets(
    asset_field, rule_field
):
    values = {
        "adset_id": "adset_1",
        "name": "Missing Copy Selector Ad",
        "page_id": "page_1",
        "destination_url": "https://example.com",
        "bodies": ["Body"],
        "image_assets": [
            {"hash": "portrait", "label": "image_feed"},
            {"hash": "story", "label": "image_story"},
        ],
        "asset_customization_rules": [
            {
                "customization_spec": {"publisher_platforms": ["facebook"]},
                "image_label": "image_feed",
                rule_field: "copy_feed",
            },
            {
                "customization_spec": {"publisher_platforms": ["instagram"]},
                "image_label": "image_story",
            },
        ],
        asset_field: [
            {"text": "Feed copy", "label": "copy_feed"},
            {"text": "Story copy", "label": "copy_story"},
        ],
    }
    if asset_field == "body_assets":
        values["bodies"] = []

    with pytest.raises(
        ValueError,
        match=f"Every asset_customization_rule must specify {rule_field}",
    ):
        AdCreateConfig.model_validate(values)


@pytest.mark.parametrize(
    ("legacy_field", "text_type", "rule_field"),
    [
        ("headlines", "headline", "title_label"),
        ("bodies", "body", "body_label"),
        ("descriptions", "description", "description_label"),
    ],
)
def test_adcreate_rejects_ambiguous_multiple_unlabeled_text_with_placement_rules(
    legacy_field, text_type, rule_field
):
    values = {
        "adset_id": "adset_1",
        "name": "Ambiguous Copy Ad",
        "page_id": "page_1",
        "destination_url": "https://example.com",
        "bodies": ["Body"],
        "image_assets": [{"hash": "portrait", "label": "image_feed"}],
        "asset_customization_rules": [
            {
                "customization_spec": {"publisher_platforms": ["facebook"]},
                "image_label": "image_feed",
            }
        ],
        legacy_field: ["Copy one", "Copy two"],
    }

    with pytest.raises(
        ValueError,
        match=(
            f"Placement customization with multiple {text_type} values requires "
            f"labeled {text_type}_assets and a {rule_field} on every rule"
        ),
    ):
        AdCreateConfig.model_validate(values)


def test_adcreate_accepts_single_unlabeled_text_for_each_type_with_placement_rules():
    cfg = AdCreateConfig(
        adset_id="adset_1",
        name="Single Copy Placement Ad",
        page_id="page_1",
        destination_url="https://example.com",
        headlines=["Headline"],
        bodies=["Body"],
        descriptions=["Description"],
        image_assets=[{"hash": "portrait", "label": "image_feed"}],
        asset_customization_rules=[
            {
                "customization_spec": {"publisher_platforms": ["facebook"]},
                "image_label": "image_feed",
            }
        ],
    )

    assert cfg.build_creative_payload()["asset_feed_spec"] == {
        "bodies": [{"text": "Body"}],
        "titles": [{"text": "Headline"}],
        "link_urls": [{"website_url": "https://example.com"}],
        "descriptions": [{"text": "Description"}],
        "images": [
            {"hash": "portrait", "adlabels": [{"name": "image_feed"}]},
        ],
        "asset_customization_rules": [
            {
                "customization_spec": {"publisher_platforms": ["facebook"]},
                "image_label": {"name": "image_feed"},
            }
        ],
        "ad_formats": ["SINGLE_IMAGE"],
        "call_to_action_types": ["LEARN_MORE"],
    }


def test_adcreate_legacy_single_image_payload_is_unchanged():
    cfg = AdCreateConfig(
        adset_id="adset_1",
        name="Ad",
        page_id="page_1",
        destination_url="https://example.com",
        headlines=["Headline"],
        bodies=["Body"],
        descriptions=["Description"],
        image_hashes=["legacy_hash"],
    )

    assert cfg.uses_asset_feed_spec() is False
    assert cfg.build_creative_payload() == {
        "name": "Ad - creative",
        "object_story_spec": {
            "page_id": "page_1",
            "link_data": {
                "message": "Body",
                "link": "https://example.com",
                "image_hash": "legacy_hash",
                "name": "Headline",
                "description": "Description",
                "call_to_action": {
                    "type": "LEARN_MORE",
                    "value": {"link": "https://example.com"},
                },
            },
        },
    }


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
headline_assets:
  - {text: Feed headline, label: headline_feed}
body_assets:
  - {text: Feed body, label: body_feed}
description_assets:
  - {text: Feed description, label: description_feed}
image_assets:
  - hash: portrait_hash
    label: feed_4x5
asset_customization_rules:
  - customization_spec:
      publisher_platforms: [facebook, instagram]
      facebook_positions: [feed]
      instagram_positions: [stream]
    image_label: feed_4x5
    title_label: headline_feed
    body_label: body_feed
    description_label: description_feed
    priority: 1
""".strip()
    )

    cfg = load_yaml_model(str(path), AdCreateConfig)
    assert cfg.headline_assets[0].label == "headline_feed"
    assert cfg.body_assets[0].label == "body_feed"
    assert cfg.description_assets[0].label == "description_feed"
    assert cfg.image_assets[0].label == "feed_4x5"
    assert cfg.asset_customization_rules[0].title_label == "headline_feed"
    assert cfg.asset_customization_rules[0].body_label == "body_feed"
    assert cfg.asset_customization_rules[0].description_label == "description_feed"
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

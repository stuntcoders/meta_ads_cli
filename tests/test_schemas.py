from __future__ import annotations

import pytest

from meta_cli.schemas import AdCreateConfig, AdSetCreateConfig


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


def test_adcreate_build_ad_payload_uses_creative_id():
    cfg = AdCreateConfig(
        adset_id="adset_1",
        name="Ad",
        existing_creative_id="123",
    )
    payload = cfg.build_ad_payload("123")
    assert payload["creative"]["creative_id"] == "123"
    assert payload["status"] == "PAUSED"

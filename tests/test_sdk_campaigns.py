from __future__ import annotations

from meta_cli.config import MetaCredentials
from meta_cli.sdk import MetaSDKClient


class FakeCampaignResult:
    def export_all_data(self):
        return {"id": "campaign_123", "status": "PAUSED"}


class FakeAccount:
    def __init__(self):
        self.params = None

    def create_campaign(self, params):
        self.params = params
        return FakeCampaignResult()


def test_create_campaign_sends_payload_to_official_sdk_account(monkeypatch):
    client = MetaSDKClient(
        MetaCredentials.model_validate(
            {
                "META_ACCESS_TOKEN": "token",
                "META_APP_ID": "app",
                "META_APP_SECRET": "secret",
                "META_AD_ACCOUNT_ID": "123",
            }
        )
    )
    account = FakeAccount()
    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_ad_account", lambda: account)
    payload = {
        "name": "Campaign",
        "objective": "OUTCOME_TRAFFIC",
        "buying_type": "AUCTION",
        "special_ad_categories": [],
        "status": "PAUSED",
    }

    result = client.create_campaign(payload)

    assert account.params == payload
    assert result == {"id": "campaign_123", "status": "PAUSED"}

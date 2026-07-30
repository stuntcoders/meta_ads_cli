from __future__ import annotations

import pytest

from meta_cli.config import MetaCredentials
from meta_cli.exceptions import APIError
from meta_cli.sdk import MetaSDKClient


class FakeCampaignResult:
    def export_all_data(self):
        return {"id": "campaign_123", "status": "PAUSED"}


class FakeCampaign:
    def __init__(self, result=True):
        self.result = result
        self.delete_calls = 0
        self.update_calls = []

    def api_update(self, params):
        self.update_calls.append(params)
        return FakeCampaignResult()

    def api_delete(self):
        self.delete_calls += 1
        return self.result


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


def test_update_campaign_budget_sends_only_daily_budget_to_official_sdk(monkeypatch):
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
    campaign = FakeCampaign()
    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_campaign", lambda campaign_id: campaign)

    result = client.update_campaign_budget("campaign_123", 1000)

    assert campaign.update_calls == [{"daily_budget": 1000}]
    assert result == {"id": "campaign_123", "status": "PAUSED"}


@pytest.mark.parametrize("method_name", ["get_campaign_details", "update_campaign_budget"])
def test_campaign_budget_operations_redact_credentials_from_api_errors(
    monkeypatch, method_name
):
    access_token = "campaign-budget-sensitive-token"
    app_secret = "campaign-budget-sensitive-secret"
    client = MetaSDKClient(
        MetaCredentials.model_validate(
            {
                "META_ACCESS_TOKEN": access_token,
                "META_APP_ID": "app",
                "META_APP_SECRET": app_secret,
                "META_AD_ACCOUNT_ID": "123",
            }
        )
    )

    class ExplodingCampaign:
        @staticmethod
        def api_get(fields):
            raise RuntimeError(f"request failed with {access_token} and {app_secret}")

        @staticmethod
        def api_update(params):
            raise RuntimeError(f"request failed with {access_token} and {app_secret}")

    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_campaign", lambda campaign_id: ExplodingCampaign())

    with pytest.raises(APIError) as exc_info:
        if method_name == "get_campaign_details":
            client.get_campaign_details("123", fields=["id", "account_id", "daily_budget"])
        else:
            client.update_campaign_budget("123", 1000)

    error = str(exc_info.value)
    assert "[REDACTED]" in error
    assert access_token not in error
    assert app_secret not in error


def test_delete_campaign_uses_official_sdk_delete(monkeypatch):
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
    campaign = FakeCampaign()
    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_campaign", lambda campaign_id: campaign)

    result = client.delete_campaign("campaign_123")

    assert campaign.delete_calls == 1
    assert result == {"success": True}

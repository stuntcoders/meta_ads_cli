from __future__ import annotations

from meta_cli.config import MetaCredentials
from meta_cli.sdk import MetaSDKClient


def _client() -> MetaSDKClient:
    credentials = MetaCredentials.model_validate(
        {
            "META_ACCESS_TOKEN": "token",
            "META_APP_ID": "app",
            "META_APP_SECRET": "secret",
            "META_AD_ACCOUNT_ID": "act_123",
        }
    )
    return MetaSDKClient(credentials)


def test_account_report_sdk_reads_metadata_adsets_and_period_insights(monkeypatch):
    client = _client()

    class Account:
        def __init__(self):
            self.calls = []

        def api_get(self, fields):
            self.calls.append(("api_get", fields))
            return {"id": "act_123", "currency": "USD"}

        def get_ad_sets(self, fields, params):
            self.calls.append(("get_ad_sets", fields, params))
            return [{"id": "s1", "campaign_id": "c1"}]

        def get_insights(self, fields, params):
            self.calls.append(("get_insights", fields, params))
            return [{"account_id": "act_123", "spend": "10.00"}]

    account = Account()
    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_ad_account", lambda: account)

    metadata = client.get_account_details(["id", "currency"])
    adsets = client.list_all_adsets(["id", "campaign_id"], limit=75)
    insights = client.get_account_insights(["account_id", "spend"], "last_30d")

    assert metadata == {"id": "act_123", "currency": "USD"}
    assert adsets == [{"id": "s1", "campaign_id": "c1"}]
    assert insights == [{"account_id": "act_123", "spend": "10.00"}]
    assert account.calls == [
        ("api_get", ["id", "currency"]),
        ("get_ad_sets", ["id", "campaign_id"], {"limit": 75}),
        (
            "get_insights",
            ["account_id", "spend"],
            {"level": "account", "date_preset": "last_30d", "limit": 100},
        ),
    ]

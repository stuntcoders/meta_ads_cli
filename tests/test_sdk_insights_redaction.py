from __future__ import annotations

import pytest

from meta_cli.config import MetaCredentials
from meta_cli.exceptions import APIError
from meta_cli.sdk import MetaSDKClient


def test_fetch_ad_insights_redacts_credentials_from_transport_errors(monkeypatch):
    access_token = "insights-sensitive-token"
    app_secret = "insights-sensitive-secret"
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

    class ExplodingAccount:
        @staticmethod
        def get_insights(fields, params):
            raise RuntimeError(
                f"request failed?access_token={access_token}&appsecret_proof={app_secret}"
            )

    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_ad_account", lambda: ExplodingAccount())

    with pytest.raises(APIError) as exc_info:
        client.get_ad_insights(fields=["spend"], date_preset="last_7d")

    error = str(exc_info.value)
    assert error.count("[REDACTED]") == 2
    assert access_token not in error
    assert app_secret not in error

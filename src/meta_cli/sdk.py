from __future__ import annotations

from dataclasses import dataclass

from meta_cli.config import MetaCredentials
from meta_cli.exceptions import APIError


@dataclass
class MetaSDKClient:
    credentials: MetaCredentials

    def _imports(self):
        try:
            from facebook_business.adobjects.adaccount import AdAccount
            from facebook_business.api import FacebookAdsApi
        except ImportError as exc:
            raise APIError(
                "facebook-business SDK is not installed. Install project dependencies first."
            ) from exc
        return FacebookAdsApi, AdAccount

    def initialize(self) -> None:
        FacebookAdsApi, _ = self._imports()
        FacebookAdsApi.init(
            app_id=self.credentials.app_id,
            app_secret=self.credentials.app_secret,
            access_token=self.credentials.access_token,
            api_version=self.credentials.api_version,
        )

    def get_ad_account(self):
        _, AdAccount = self._imports()
        return AdAccount(self.credentials.ad_account_id)

    def test_auth(self) -> dict:
        self.initialize()
        account = self.get_ad_account()
        try:
            result = account.api_get(fields=["id", "name", "account_status"])
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to authenticate or access ad account: {exc}") from exc
        return {
            "id": result.get("id"),
            "name": result.get("name"),
            "account_status": result.get("account_status"),
        }

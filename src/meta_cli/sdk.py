from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from meta_cli.config import MetaCredentials
from meta_cli.exceptions import APIError


@dataclass
class MetaSDKClient:
    credentials: MetaCredentials

    def _core_imports(self) -> Tuple[Any, Any]:
        try:
            from facebook_business.adobjects.adaccount import AdAccount
            from facebook_business.api import FacebookAdsApi
        except ImportError as exc:
            raise APIError(
                "facebook-business SDK is not installed. Install project dependencies first."
            ) from exc
        return FacebookAdsApi, AdAccount

    def _import_class(self, module_path: str, class_name: str) -> Any:
        try:
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to import SDK class {class_name}: {exc}") from exc

    def initialize(self) -> None:
        FacebookAdsApi, _ = self._core_imports()
        FacebookAdsApi.init(
            app_id=self.credentials.app_id,
            app_secret=self.credentials.app_secret,
            access_token=self.credentials.access_token,
            api_version=self.credentials.api_version,
        )

    @staticmethod
    def to_dict(obj: Any) -> Dict[str, Any]:
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "export_all_data"):
            return obj.export_all_data()
        return dict(obj)

    def get_ad_account(self):
        _, AdAccount = self._core_imports()
        return AdAccount(self.credentials.ad_account_id)

    def get_campaign(self, campaign_id: str):
        Campaign = self._import_class("facebook_business.adobjects.campaign", "Campaign")
        return Campaign(campaign_id)

    def get_adset(self, adset_id: str):
        AdSet = self._import_class("facebook_business.adobjects.adset", "AdSet")
        return AdSet(adset_id)

    def get_ad(self, ad_id: str):
        Ad = self._import_class("facebook_business.adobjects.ad", "Ad")
        return Ad(ad_id)

    def test_auth(self) -> Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        try:
            result = account.api_get(fields=["id", "name", "account_status"])
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to authenticate or access ad account: {exc}") from exc
        data = self.to_dict(result)
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "account_status": data.get("account_status"),
        }

    def list_campaigns(self, fields: List[str], limit: int = 50) -> List[Dict[str, Any]]:
        self.initialize()
        account = self.get_ad_account()
        try:
            cursor = account.get_campaigns(fields=fields, params={"limit": limit})
            return [self.to_dict(item) for item in cursor]
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to list campaigns: {exc}") from exc

    def list_adsets(self, campaign_id: str, fields: List[str], limit: int = 100) -> List[Dict[str, Any]]:
        self.initialize()
        campaign = self.get_campaign(campaign_id)
        try:
            cursor = campaign.get_ad_sets(fields=fields, params={"limit": limit})
            return [self.to_dict(item) for item in cursor]
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to list ad sets for campaign {campaign_id}: {exc}") from exc

    def list_ads(self, adset_id: str, fields: List[str], limit: int = 100) -> List[Dict[str, Any]]:
        self.initialize()
        adset = self.get_adset(adset_id)
        try:
            cursor = adset.get_ads(fields=fields, params={"limit": limit})
            return [self.to_dict(item) for item in cursor]
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to list ads for ad set {adset_id}: {exc}") from exc

    def list_all_ads(self, fields: List[str], limit: int = 200) -> List[Dict[str, Any]]:
        self.initialize()
        account = self.get_ad_account()
        try:
            cursor = account.get_ads(fields=fields, params={"limit": limit})
            return [self.to_dict(item) for item in cursor]
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to list all ads: {exc}") from exc

    def get_ad_insights(
        self,
        fields: List[str],
        date_preset: str | None = None,
        since: str | None = None,
        until: str | None = None,
        adset_id: str | None = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        self.initialize()
        params: Dict[str, Any] = {"level": "ad", "limit": limit}
        if date_preset:
            params["date_preset"] = date_preset
        elif since and until:
            params["time_range"] = {"since": since, "until": until}
        elif since or until:
            raise APIError("Both --since and --until must be supplied together")

        try:
            if adset_id:
                adset = self.get_adset(adset_id)
                cursor = adset.get_insights(fields=fields, params=params)
            else:
                account = self.get_ad_account()
                cursor = account.get_insights(fields=fields, params=params)
            return [self.to_dict(item) for item in cursor]
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to fetch ad insights: {exc}") from exc

    def upload_image(self, image_path: str) -> Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        path = Path(image_path)
        if not path.exists():
            raise APIError(f"Image file does not exist: {image_path}")
        try:
            result = account.create_ad_image(params={"filename": str(path)})
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to upload image: {exc}") from exc
        return self.to_dict(result)

    def upload_video(self, video_path: str) -> Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        path = Path(video_path)
        if not path.exists():
            raise APIError(f"Video file does not exist: {video_path}")
        try:
            result = account.create_ad_video(params={"filepath": str(path)})
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to upload video: {exc}") from exc
        return self.to_dict(result)

    def create_adset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        try:
            result = account.create_ad_set(params=payload)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to create ad set: {exc}") from exc
        return self.to_dict(result)

    def create_creative(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        try:
            result = account.create_ad_creative(params=payload)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to create creative: {exc}") from exc
        return self.to_dict(result)

    def create_ad(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        try:
            result = account.create_ad(params=payload)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to create ad: {exc}") from exc
        return self.to_dict(result)

    def update_campaign_status(self, campaign_id: str, status: str) -> Dict[str, Any]:
        self.initialize()
        campaign = self.get_campaign(campaign_id)
        try:
            result = campaign.api_update(params={"status": status})
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to update campaign {campaign_id}: {exc}") from exc
        return self.to_dict(result)

    def update_adset_status(self, adset_id: str, status: str) -> Dict[str, Any]:
        self.initialize()
        adset = self.get_adset(adset_id)
        try:
            result = adset.api_update(params={"status": status})
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to update ad set {adset_id}: {exc}") from exc
        return self.to_dict(result)

    def update_ad_status(self, ad_id: str, status: str) -> Dict[str, Any]:
        self.initialize()
        ad = self.get_ad(ad_id)
        try:
            result = ad.api_update(params={"status": status})
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to update ad {ad_id}: {exc}") from exc
        return self.to_dict(result)

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

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

    @staticmethod
    def _with_pagination_params(
        base_params: Dict[str, Any],
        after: str | None,
        before: str | None,
    ) -> Dict[str, Any]:
        params = dict(base_params)
        if after and before:
            raise APIError("Use either --after or --before, not both")
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        return params

    @staticmethod
    def _paginated_result(data: List[Dict[str, Any]], paging: Dict[str, Any]) -> Dict[str, Any]:
        return {"data": data, "paging": paging}

    def _collect_cursor(
        self,
        cursor: Any,
        auto_paginate: bool = True,
        max_pages: int | None = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if max_pages is not None and max_pages < 1:
            raise APIError("max_pages must be >= 1")

        if hasattr(cursor, "load_next_page"):
            rows: List[Dict[str, Any]] = []
            pages_read = 0
            initial_params = getattr(cursor, "params", {}) or {}
            requested_after = initial_params.get("after")
            requested_before = initial_params.get("before")

            while cursor.load_next_page():
                pages_read += 1
                current_items = [self.to_dict(cursor[i]) for i in range(len(cursor))]
                rows.extend(current_items)

                if hasattr(cursor, "_queue"):
                    cursor._queue = []

                if not auto_paginate:
                    break
                if max_pages is not None and pages_read >= max_pages:
                    break

            current_params = getattr(cursor, "params", {}) or {}
            has_more = None
            if hasattr(cursor, "_finished_iteration"):
                has_more = not bool(cursor._finished_iteration)

            next_after = current_params.get("after") if has_more else None
            total_count = None
            if hasattr(cursor, "total"):
                try:
                    total_count = cursor.total()
                except Exception:  # noqa: BLE001
                    total_count = None

            paging = {
                "requested_after": requested_after,
                "requested_before": requested_before,
                "next_after": next_after,
                "has_more": has_more,
                "pages_fetched": pages_read,
                "total_count": total_count,
            }
            return rows, paging

        rows = [self.to_dict(item) for item in cursor]
        paging = {
            "requested_after": None,
            "requested_before": None,
            "next_after": None,
            "has_more": None,
            "pages_fetched": 1 if rows else 0,
            "total_count": None,
        }
        return rows, paging

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

    def get_video(self, video_id: str):
        AdVideo = self._import_class("facebook_business.adobjects.advideo", "AdVideo")
        return AdVideo(video_id)

    @staticmethod
    def parse_video_processing_status(video_data: Dict[str, Any]) -> Dict[str, Any]:
        status_obj = video_data.get("status")
        progress = None
        states: List[str] = []

        def _extract_from_mapping(mapping: Dict[str, Any]) -> None:
            nonlocal progress
            for key in ["video_status", "processing_status", "status", "state", "phase"]:
                value = mapping.get(key)
                if isinstance(value, str):
                    states.append(value.lower())
            for key in [
                "processing_progress",
                "progress",
                "progress_percent",
                "processing_percentage",
            ]:
                value = mapping.get(key)
                if isinstance(value, (int, float)):
                    progress = int(value)
            for value in mapping.values():
                if isinstance(value, dict):
                    _extract_from_mapping(value)

        if isinstance(status_obj, dict):
            _extract_from_mapping(status_obj)
        if isinstance(video_data.get("processing_progress"), (int, float)):
            progress = int(video_data.get("processing_progress"))
        if isinstance(video_data.get("video_status"), str):
            states.append(video_data.get("video_status").lower())

        state = states[0] if states else "unknown"

        success_states = {"ready", "finished", "available", "completed", "success"}
        failed_states = {"error", "failed", "rejected", "timeout"}

        is_failed = any(candidate in failed_states for candidate in states)
        is_complete = (progress is not None and progress >= 100) or any(
            candidate in success_states for candidate in states
        )

        return {
            "state": state,
            "progress": progress,
            "is_complete": bool(is_complete and not is_failed),
            "is_failed": is_failed,
            "raw_status": status_obj,
        }

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

    def list_campaigns(
        self,
        fields: List[str],
        limit: int = 50,
        after: str | None = None,
        before: str | None = None,
        auto_paginate: bool = True,
        max_pages: int | None = None,
        include_paging: bool = False,
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        params = self._with_pagination_params({"limit": limit}, after, before)
        try:
            cursor = account.get_campaigns(fields=fields, params=params)
            rows, paging = self._collect_cursor(
                cursor,
                auto_paginate=auto_paginate,
                max_pages=max_pages,
            )
            if include_paging:
                return self._paginated_result(rows, paging)
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to list campaigns: {exc}") from exc

    def list_adsets(
        self,
        campaign_id: str,
        fields: List[str],
        limit: int = 100,
        after: str | None = None,
        before: str | None = None,
        auto_paginate: bool = True,
        max_pages: int | None = None,
        include_paging: bool = False,
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        self.initialize()
        campaign = self.get_campaign(campaign_id)
        params = self._with_pagination_params({"limit": limit}, after, before)
        try:
            cursor = campaign.get_ad_sets(fields=fields, params=params)
            rows, paging = self._collect_cursor(
                cursor,
                auto_paginate=auto_paginate,
                max_pages=max_pages,
            )
            if include_paging:
                return self._paginated_result(rows, paging)
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to list ad sets for campaign {campaign_id}: {exc}") from exc

    def list_ads(
        self,
        adset_id: str,
        fields: List[str],
        limit: int = 100,
        after: str | None = None,
        before: str | None = None,
        auto_paginate: bool = True,
        max_pages: int | None = None,
        include_paging: bool = False,
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        self.initialize()
        adset = self.get_adset(adset_id)
        params = self._with_pagination_params({"limit": limit}, after, before)
        try:
            cursor = adset.get_ads(fields=fields, params=params)
            rows, paging = self._collect_cursor(
                cursor,
                auto_paginate=auto_paginate,
                max_pages=max_pages,
            )
            if include_paging:
                return self._paginated_result(rows, paging)
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to list ads for ad set {adset_id}: {exc}") from exc

    def list_all_ads(
        self,
        fields: List[str],
        limit: int = 200,
        after: str | None = None,
        before: str | None = None,
        auto_paginate: bool = True,
        max_pages: int | None = None,
        include_paging: bool = False,
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        params = self._with_pagination_params({"limit": limit}, after, before)
        try:
            cursor = account.get_ads(fields=fields, params=params)
            rows, paging = self._collect_cursor(
                cursor,
                auto_paginate=auto_paginate,
                max_pages=max_pages,
            )
            if include_paging:
                return self._paginated_result(rows, paging)
            return rows
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
        after: str | None = None,
        before: str | None = None,
        auto_paginate: bool = True,
        max_pages: int | None = None,
        include_paging: bool = False,
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        self.initialize()
        params: Dict[str, Any] = self._with_pagination_params(
            {"level": "ad", "limit": limit},
            after,
            before,
        )
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
            rows, paging = self._collect_cursor(
                cursor,
                auto_paginate=auto_paginate,
                max_pages=max_pages,
            )
            if include_paging:
                return self._paginated_result(rows, paging)
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to fetch ad insights: {exc}") from exc

    def get_video_status(self, video_id: str) -> Dict[str, Any]:
        self.initialize()
        video = self.get_video(video_id)
        try:
            result = video.api_get(fields=["id", "status", "processing_progress", "updated_time"])
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to fetch video status for {video_id}: {exc}") from exc
        return self.to_dict(result)

    def wait_for_video_processing(
        self,
        video_id: str,
        poll_interval: float = 5.0,
        timeout: int = 1800,
        on_update: Callable[[Dict[str, Any]], None] | None = None,
    ) -> Dict[str, Any]:
        if poll_interval <= 0:
            raise APIError("poll_interval must be greater than 0")
        if timeout <= 0:
            raise APIError("timeout must be greater than 0")

        started = time.monotonic()
        latest: Dict[str, Any] = {}

        while True:
            status_payload = self.get_video_status(video_id)
            parsed = self.parse_video_processing_status(status_payload)
            elapsed = time.monotonic() - started
            latest = {
                "video_id": video_id,
                "elapsed_seconds": round(elapsed, 2),
                **parsed,
                "status": status_payload,
            }

            if on_update:
                on_update(latest)

            if parsed["is_failed"]:
                raise APIError(
                    f"Video processing failed for {video_id} with state '{parsed['state']}'."
                )
            if parsed["is_complete"]:
                return latest
            if elapsed >= timeout:
                raise APIError(
                    f"Timed out waiting for video {video_id} processing after {timeout}s. "
                    f"Last state='{parsed['state']}', progress={parsed['progress']}"
                )

            time.sleep(poll_interval)

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

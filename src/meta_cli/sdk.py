from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from meta_cli.config import MetaCredentials
from meta_cli.exceptions import APIError


class _IdentityResponseParser:
    """Do not mistake an SDK constructor ID for identity returned by Meta."""

    def __init__(self, parser, expected_id: str):
        self.parser = parser
        self.expected_id = expected_id

    def parse_single(self, response):
        data = response.get("data", response) if isinstance(response, dict) else None
        if not isinstance(data, dict) or str(data.get("id")) != self.expected_id:
            raise APIError("Target lookup did not return the requested ID")
        for envelope in (response, data):
            if "error" in envelope or (
                "success" in envelope and envelope["success"] is not True
            ):
                raise APIError("Meta did not confirm the target lookup")
        # The SDK drops null fields on export. Reject an explicit unsafe shape
        # before parsing so null cannot become absence and trigger edge fallback.
        if "adlabels" in data and not isinstance(data["adlabels"], list):
            raise APIError("Target adlabels must be an explicit list; missing/partial labels are unsafe")
        return self.parser.parse_single(response)


class _CompleteLabelEdgeParser:
    """Validate raw label pages before the SDK's permissive ObjectParser.

    A missing node field is not an empty set. Only a valid terminal edge page
    establishes completeness, including when intermediate pages contain no rows.
    """

    def __init__(self, parser):
        self.parser = parser
        self.complete = False
        self.pages = 0
        self.seen_after: set[str] = set()
        self.seen_ids: set[str] = set()

    def parse_multiple(self, response):
        if (not isinstance(response, dict) or not isinstance(response.get("data"), list)
                or "error" in response
                or ("success" in response and response["success"] is not True)):
            raise APIError("Target label edge returned an invalid page")
        paging = response.get("paging", {})
        if not isinstance(paging, dict):
            raise APIError("Target label edge returned invalid pagination")
        cursors = paging.get("cursors", {})
        if not isinstance(cursors, dict):
            raise APIError("Target label edge returned invalid cursors")
        for key in ("before", "after"):
            if key in cursors and (not isinstance(cursors[key], str) or not cursors[key]):
                raise APIError("Target label edge returned an invalid cursor")
        has_next = "next" in paging
        if has_next:
            after = cursors.get("after")
            if not isinstance(paging["next"], str) or not paging["next"] or not after:
                raise APIError("Target label edge pagination is incomplete")
            if after in self.seen_after:
                raise APIError("Target label edge pagination did not progress")
            self.seen_after.add(after)

        ids = []
        for row in response["data"]:
            if (not isinstance(row, dict) or "error" in row
                    or ("success" in row and row["success"] is not True)):
                raise APIError("Target label edge contains an invalid label")
            label_id = str(row.get("id", ""))
            if not label_id.isascii() or not label_id.isdigit():
                raise APIError("Target label edge contains an invalid label ID")
            if label_id in self.seen_ids:
                raise APIError("Target label edge contains duplicate IDs; retry the read")
            self.seen_ids.add(label_id)
            ids.append(label_id)
        objects = self.parser.parse_multiple(response)
        if not isinstance(objects, list) or [str(obj.get("id")) for obj in objects] != ids:
            raise APIError("SDK did not preserve the target label edge page")
        self.pages += 1
        self.complete = not has_next
        return objects


class _CheckedMutationParser:
    """Check acknowledgements before ObjectParser discards the success flag."""

    def __init__(self, parser, *, expected_id: str | None, allow_empty: bool):
        self.parser = parser
        self.expected_id = expected_id
        self.allow_empty = allow_empty

    def parse_single(self, response):
        if not isinstance(response, dict):
            raise APIError("Meta returned an invalid mutation response")
        data = response.get("data", response)
        if not isinstance(data, dict):
            raise APIError("Meta returned an invalid mutation response")
        for envelope in (response, data):
            if "error" in envelope or (
                "success" in envelope and envelope["success"] is not True
            ):
                raise APIError("Meta did not acknowledge the mutation")
            if "id" in envelope:
                returned_id = str(envelope["id"])
                if (not returned_id.isascii() or not returned_id.isdigit()
                        or (self.expected_id is not None and returned_id != self.expected_id)):
                    raise APIError("Meta mutation response did not match the expected ID")
        if not (data.get("success") is True or "id" in data
                or (self.allow_empty and not data)):
            raise APIError("Meta did not acknowledge the mutation")
        # Keep the official parser, including its empty success-only result.
        # This is NOT verification: callers must read back the affected object.
        return self.parser.parse_single(response)


def _execute_checked_mutation(request, *, expected_id=None, allow_empty=False):
    # Generated methods expose pending=True but no public parser setter. Wrap
    # only this request's parser; never patch SDK globals or replace transport.
    parser = request._response_parser
    if parser is None:
        raise APIError("SDK mutation request has no response parser")
    request._response_parser = _CheckedMutationParser(
        parser, expected_id=expected_id, allow_empty=allow_empty,
    )
    return request.execute()


@dataclass
class MetaSDKClient:
    credentials: MetaCredentials
    active_environment: str | None = None

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

    def _redact_exception(self, exc: Exception) -> str:
        message = str(exc)
        for secret in (self.credentials.access_token, self.credentials.app_secret):
            if secret:
                message = message.replace(secret, "[REDACTED]")
        return message

    def initialize(self) -> None:
        FacebookAdsApi, _ = self._core_imports()
        try:
            FacebookAdsApi.init(
                app_id=self.credentials.app_id,
                app_secret=self.credentials.app_secret,
                access_token=self.credentials.access_token,
                api_version=self.credentials.api_version,
            )
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to initialize Meta authentication: {self._redact_exception(exc)}"
            ) from exc

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

            def _consume_current_page() -> None:
                nonlocal pages_read
                current_items = [self.to_dict(cursor[i]) for i in range(len(cursor))]
                if current_items:
                    rows.extend(current_items)
                    pages_read += 1
                if hasattr(cursor, "_queue"):
                    cursor._queue = []

            # Some SDK cursors are preloaded with the first page immediately.
            # Consume that page first so we don't drop rows when load_next_page()
            # returns False right away.
            if len(cursor) > 0:
                _consume_current_page()

            while True:
                if not auto_paginate and pages_read > 0:
                    break
                if max_pages is not None and pages_read >= max_pages:
                    break

                has_next_page = cursor.load_next_page()
                if not has_next_page:
                    break

                _consume_current_page()

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

    def get_object_label_details(
        self, object_type: str, object_id: str, fields: List[str],
    ) -> Dict[str, Any]:
        """Read label state with transport-returned identity, not a reused SDK ID."""
        if object_type not in {"ad", "campaign"}:
            raise APIError("Only ads and campaigns support additive labeling")
        self.initialize()
        try:
            target = self.get_ad(object_id) if object_type == "ad" else self.get_campaign(object_id)
            request = target.api_get(fields=fields, pending=True)
            request._response_parser = _IdentityResponseParser(request._response_parser, object_id)
            return self.to_dict(request.execute())
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to fetch {object_type} {object_id}: {self._redact_exception(exc)}"
            ) from exc

    def list_object_labels(self, object_type: str, object_id: str) -> List[Dict[str, Any]]:
        """Resolve the entire target /adlabels GET edge, or fail without a result.

        Use only as fallback for an absent node field, after caller ownership
        checks. Explicit null/partial node fields must still fail closed.
        """
        if object_type not in {"ad", "campaign"}:
            raise APIError("Only ads and campaigns support additive labeling")
        if not isinstance(object_id, str) or not object_id.isascii() or not object_id.isdigit():
            raise APIError("Object ID must be numeric")
        self.initialize()
        try:
            from facebook_business.adobjects.adlabel import AdLabel
            from facebook_business.adobjects.objectparser import ObjectParser
            from facebook_business.api import Cursor

            target = self.get_ad(object_id) if object_type == "ad" else self.get_campaign(object_id)
            parser = _CompleteLabelEdgeParser(ObjectParser(api=target.get_api(), target_class=AdLabel))
            # Ads/campaigns have no generated get_ad_labels. Use the official
            # Cursor with a scoped parser, not raw HTTP or a global SDK patch.
            cursor = Cursor(
                source_object=target, target_objects_class=AdLabel,
                fields=["id", "name"], endpoint="adlabels", include_summary=False,
                object_parser=parser,
            )
            rows = []
            while not parser.complete:
                pages_before = parser.pages
                # False means an empty *page*, not necessarily the end. Do not
                # use list(cursor) or _collect_cursor here: both can stop early.
                cursor.load_next_page()
                if parser.pages != pages_before + 1:
                    raise APIError("Target label edge completion could not be established")
                rows.extend(self.to_dict(cursor[i]) for i in range(len(cursor)))
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to resolve complete labels for {object_type} {object_id}: "
                f"{self._redact_exception(exc)}"
            ) from exc

    def add_object_label(self, object_type: str, object_id: str, label_id: str) -> None:
        """POST only the new ID to the additive edge, never replace node adlabels.

        Caller owns account/label preflight, confirmation and mandatory readback.
        """
        if object_type not in {"ad", "campaign"}:
            raise APIError("Only ads and campaigns support additive labeling")
        if any(not isinstance(value, str) or not value.isascii() or not value.isdigit()
               for value in (object_id, label_id)):
            raise APIError("Object and label IDs must be numeric")
        self.initialize()
        try:
            target = self.get_ad(object_id) if object_type == "ad" else self.get_campaign(object_id)
            request = target.create_ad_label(
                params={"adlabels": [{"id": label_id}]}, pending=True,
            )
            _execute_checked_mutation(request, expected_id=object_id, allow_empty=True)
            # The SDK strips success-only acknowledgements to {}. Returning
            # here permits mandatory caller readback, not a success claim.
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Additive label write for {object_type} {object_id} is unconfirmed. "
                "Fetch the object before retrying: " + self._redact_exception(exc)
            ) from exc

    def get_creative(self, creative_id: str):
        AdCreative = self._import_class(
            "facebook_business.adobjects.adcreative", "AdCreative"
        )
        return AdCreative(creative_id)

    def get_custom_conversion(self, custom_conversion_id: str):
        CustomConversion = self._import_class(
            "facebook_business.adobjects.customconversion", "CustomConversion"
        )
        return CustomConversion(custom_conversion_id)

    def get_custom_audience(self, custom_audience_id: str):
        CustomAudience = self._import_class(
            "facebook_business.adobjects.customaudience", "CustomAudience"
        )
        return CustomAudience(custom_audience_id)

    def get_video(self, video_id: str):
        AdVideo = self._import_class("facebook_business.adobjects.advideo", "AdVideo")
        return AdVideo(video_id)

    def get_account_details(self, fields: List[str]) -> Dict[str, Any]:
        self.initialize()
        try:
            account = self.get_ad_account()
            return self.to_dict(account.api_get(fields=fields))
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to fetch ad account metadata: {self._redact_exception(exc)}"
            ) from exc

    def get_campaign_details(self, campaign_id: str, fields: List[str]) -> Dict[str, Any]:
        self.initialize()
        campaign = self.get_campaign(campaign_id)
        try:
            return self.to_dict(campaign.api_get(fields=fields))
        except Exception as exc:  # noqa: BLE001
            message = self._redact_exception(exc)
            raise APIError(f"Failed to fetch campaign {campaign_id}: {message}") from exc

    def get_adset_details(self, adset_id: str, fields: List[str]) -> Dict[str, Any]:
        self.initialize()
        adset = self.get_adset(adset_id)
        try:
            result = adset.api_get(fields=fields)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to fetch ad set {adset_id}: {exc}") from exc
        return self.to_dict(result)

    def get_ad_details(self, ad_id: str, fields: List[str]) -> Dict[str, Any]:
        self.initialize()
        try:
            ad = self.get_ad(ad_id)
            return self.to_dict(ad.api_get(fields=fields))
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to fetch ad {ad_id}: {self._redact_exception(exc)}"
            ) from exc

    def get_creative_details(self, creative_id: str, fields: List[str]) -> Dict[str, Any]:
        self.initialize()
        creative = self.get_creative(creative_id)
        try:
            result = creative.api_get(fields=fields)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to fetch creative {creative_id}: {exc}") from exc
        return self.to_dict(result)

    def get_custom_conversion_details(
        self, custom_conversion_id: str, fields: List[str]
    ) -> Dict[str, Any]:
        self.initialize()
        custom_conversion = self.get_custom_conversion(custom_conversion_id)
        try:
            result = custom_conversion.api_get(fields=fields)
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to fetch custom conversion {custom_conversion_id}: {exc}"
            ) from exc
        return self.to_dict(result)

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
            raise APIError(
                "Failed to authenticate or access ad account: "
                f"{self._redact_exception(exc)}"
            ) from exc
        data = self.to_dict(result)
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "account_status": data.get("account_status"),
        }

    def list_ad_labels(
        self,
        fields: List[str],
        limit: int = 50,
        after: str | None = None,
        before: str | None = None,
        auto_paginate: bool = True,
        max_pages: int | None = None,
        include_paging: bool = False,
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        params = self._with_pagination_params({"limit": limit}, after, before)
        if not 1 <= limit <= 500:
            raise APIError("limit must be between 1 and 500")
        if max_pages is not None and max_pages < 1:
            raise APIError("max_pages must be >= 1")
        self.initialize()
        try:
            account = self.get_ad_account()
            cursor = account.get_ad_labels(fields=fields, params=params)
            rows, paging = self._collect_cursor(
                cursor, auto_paginate=auto_paginate, max_pages=max_pages
            )
            if include_paging:
                return self._paginated_result(rows, paging)
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to list account labels: {self._redact_exception(exc)}"
            ) from exc

    def create_ad_label(self, name: str) -> Dict[str, Any]:
        if not isinstance(name, str) or not name.strip():
            raise APIError("Label name must not be blank")
        self.initialize()
        try:
            account = self.get_ad_account()
            request = account.create_ad_label(params={"name": name}, pending=True)
            result = self.to_dict(_execute_checked_mutation(request))
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                "Label creation failed; the write outcome may be unknown. "
                "List account labels before retrying: "
                f"{self._redact_exception(exc)}"
            ) from exc
        label_id = str(result.get("id") or "")
        if result.get("success") is False or not label_id.isascii() or not label_id.isdigit():
            raise APIError(
                "Meta did not return a valid created label ID. "
                "The write outcome is unconfirmed; list account labels before retrying."
            )
        return {"id": label_id}

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

    def list_all_adsets(
        self,
        fields: List[str],
        limit: int = 200,
        auto_paginate: bool = True,
        max_pages: int | None = None,
    ) -> List[Dict[str, Any]]:
        self.initialize()
        account = self.get_ad_account()
        try:
            cursor = account.get_ad_sets(fields=fields, params={"limit": limit})
            rows, _ = self._collect_cursor(
                cursor,
                auto_paginate=auto_paginate,
                max_pages=max_pages,
            )
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to list account ad sets: {exc}") from exc

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

    def list_custom_conversions(
        self,
        fields: List[str],
        limit: int = 100,
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
            cursor = account.get_custom_conversions(fields=fields, params=params)
            rows, paging = self._collect_cursor(
                cursor,
                auto_paginate=auto_paginate,
                max_pages=max_pages,
            )
            if include_paging:
                return self._paginated_result(rows, paging)
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to list custom conversions: {exc}") from exc

    def list_custom_audiences(
        self,
        fields: List[str],
        limit: int = 100,
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
            cursor = account.get_custom_audiences(fields=fields, params=params)
            rows, paging = self._collect_cursor(
                cursor,
                auto_paginate=auto_paginate,
                max_pages=max_pages,
            )
            if include_paging:
                return self._paginated_result(rows, paging)
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to list custom audiences: {exc}") from exc

    def get_custom_audience_details(
        self, custom_audience_id: str, fields: List[str]
    ) -> Dict[str, Any]:
        self.initialize()
        audience = self.get_custom_audience(custom_audience_id)
        try:
            result = audience.api_get(fields=fields)
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to get custom audience {custom_audience_id}: {exc}"
            ) from exc
        return self.to_dict(result)

    def create_custom_audience(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        try:
            result = account.create_custom_audience(params=payload)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to create custom audience: {exc}") from exc
        return self.to_dict(result)

    def search_targeting_interests(self, query: str) -> List[Dict[str, Any]]:
        self.initialize()
        try:
            TargetingSearch = self._import_class(
                "facebook_business.adobjects.targetingsearch", "TargetingSearch"
            )
            results = TargetingSearch.search(
                params={"q": query, "type": "adinterest"}
            )
            return [self.to_dict(item) for item in results]
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to search targeting interests for '{query}': {exc}") from exc

    def search_targeting_categories(
        self, demographic_class: str
    ) -> List[Dict[str, Any]]:
        self.initialize()
        try:
            TargetingSearch = self._import_class(
                "facebook_business.adobjects.targetingsearch", "TargetingSearch"
            )
            results = TargetingSearch.search(
                params={"type": "adtargetingcategory", "class": demographic_class}
            )
            return [self.to_dict(item) for item in results]
        except Exception as exc:  # noqa: BLE001
            message = self._redact_exception(exc)
            raise APIError(
                f"Failed to search targeting category class '{demographic_class}': {message}"
            ) from exc

    def search_targeting_locations(
        self, query: str, countries: List[str] | None = None
    ) -> List[Dict[str, Any]]:
        self.initialize()
        try:
            TargetingSearch = self._import_class(
                "facebook_business.adobjects.targetingsearch", "TargetingSearch"
            )
            results = TargetingSearch.search(
                params={
                    "q": query,
                    "type": "adgeolocation",
                    "location_types": ["city", "region"],
                }
            )
            rows = [self.to_dict(item) for item in results]
            if countries:
                country_codes = {country.upper() for country in countries}
                rows = [row for row in rows if row.get("country_code") in country_codes]
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to search targeting locations for '{query}': {exc}") from exc

    def get_account_insights(
        self,
        fields: List[str],
        date_preset: str,
    ) -> List[Dict[str, Any]]:
        self.initialize()
        account = self.get_ad_account()
        params = {"level": "account", "date_preset": date_preset, "limit": 100}
        try:
            cursor = account.get_insights(fields=fields, params=params)
            rows, _ = self._collect_cursor(cursor, auto_paginate=True)
            return rows
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to fetch account insights for date preset {date_preset}: {exc}"
            ) from exc

    def get_ad_insights(
        self,
        fields: List[str],
        date_preset: str | None = None,
        since: str | None = None,
        until: str | None = None,
        breakdowns: List[str] | None = None,
        time_increment: int | None = None,
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
        if breakdowns:
            params["breakdowns"] = breakdowns
        if time_increment is not None:
            params["time_increment"] = time_increment

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
            message = self._redact_exception(exc)
            raise APIError(f"Failed to fetch ad insights: {message}") from exc

    def get_video_status(self, video_id: str) -> Dict[str, Any]:
        self.initialize()
        video = self.get_video(video_id)
        try:
            result = video.api_get(fields=["id", "status", "updated_time"])
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
            result = account.create_ad_video(params={"source": str(path)})
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to upload video: {exc}") from exc
        return self.to_dict(result)

    def create_campaign(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        try:
            result = account.create_campaign(params=payload)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to create campaign: {exc}") from exc
        return self.to_dict(result)

    def create_adset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        try:
            result = account.create_ad_set(params=payload)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to create ad set: {exc}") from exc
        return self.to_dict(result)

    def create_custom_conversion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.initialize()
        account = self.get_ad_account()
        try:
            result = account.create_custom_conversion(params=payload)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to create custom conversion: {exc}") from exc
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

    def update_campaign_budget(self, campaign_id: str, daily_budget: int) -> Dict[str, Any]:
        self.initialize()
        campaign = self.get_campaign(campaign_id)
        try:
            result = campaign.api_update(params={"daily_budget": daily_budget})
        except Exception as exc:  # noqa: BLE001
            message = self._redact_exception(exc)
            raise APIError(
                f"Failed to update daily budget for campaign {campaign_id}: {message}"
            ) from exc
        return self.to_dict(result)

    def delete_campaign(self, campaign_id: str) -> Dict[str, Any]:
        self.initialize()
        campaign = self.get_campaign(campaign_id)
        try:
            result = campaign.api_delete()
        except Exception as exc:  # noqa: BLE001
            message = self._redact_exception(exc)
            raise APIError(f"Failed to delete campaign {campaign_id}: {message}") from exc

        if isinstance(result, bool):
            if not result:
                raise APIError(f"Meta did not confirm deletion of campaign {campaign_id}")
            return {"success": True}

        payload = self.to_dict(result)
        if payload.get("success") is False:
            raise APIError(f"Meta did not confirm deletion of campaign {campaign_id}")
        return payload

    def update_adset_status(self, adset_id: str, status: str) -> Dict[str, Any]:
        self.initialize()
        adset = self.get_adset(adset_id)
        try:
            result = adset.api_update(params={"status": status})
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to update ad set {adset_id}: {exc}") from exc
        return self.to_dict(result)

    def update_adset_budget(self, adset_id: str, budget: Dict[str, int]) -> Dict[str, Any]:
        self.initialize()
        adset = self.get_adset(adset_id)
        try:
            result = adset.api_update(params=budget)
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to update budget for ad set {adset_id}: {exc}") from exc
        return self.to_dict(result)

    def update_adset_targeting(
        self, adset_id: str, targeting: Dict[str, Any]
    ) -> Dict[str, Any]:
        self.initialize()
        adset = self.get_adset(adset_id)
        try:
            result = adset.api_update(params={"targeting": targeting})
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to update targeting for ad set {adset_id}: {exc}") from exc
        return self.to_dict(result)

    def update_adset_attribution(
        self, adset_id: str, attribution_spec: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        self.initialize()
        adset = self.get_adset(adset_id)
        try:
            result = adset.api_update(params={"attribution_spec": attribution_spec})
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to update attribution spec for ad set {adset_id}: {exc}"
            ) from exc
        return self.to_dict(result)

    def update_ad_status(self, ad_id: str, status: str) -> Dict[str, Any]:
        self.initialize()
        try:
            ad = self.get_ad(ad_id)
            if status == "ARCHIVED":
                request = ad.api_update(params={"status": status}, pending=True)
                return self.to_dict(_execute_checked_mutation(request, expected_id=ad_id))
            return self.to_dict(ad.api_update(params={"status": status}))
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                f"Failed to update ad {ad_id}: {self._redact_exception(exc)}"
            ) from exc

    def update_ad_creative(self, ad_id: str, creative_id: str) -> Dict[str, Any]:
        self.initialize()
        ad = self.get_ad(ad_id)
        try:
            result = ad.api_update(params={"creative": {"creative_id": creative_id}})
        except Exception as exc:  # noqa: BLE001
            raise APIError(f"Failed to update creative for ad {ad_id}: {exc}") from exc
        return self.to_dict(result)

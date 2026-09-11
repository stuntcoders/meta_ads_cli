from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adlabel import AdLabel
from facebook_business.adobjects.campaign import Campaign
from facebook_business.api import FacebookAdsApi
from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.commands import ads, campaigns
from meta_cli.config import MetaCredentials
from meta_cli.sdk import MetaSDKClient

runner = CliRunner()


@pytest.fixture(autouse=True)
def offline_only(monkeypatch, tmp_path):
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(tmp_path / "environments.yaml"))
    monkeypatch.delenv("META_CLI_ENVIRONMENT", raising=False)

    def reject_api_call(*args, **kwargs):
        pytest.fail("Verification getter tests must not contact Meta")

    monkeypatch.setattr(FacebookAdsApi, "call", reject_api_call)


@pytest.fixture(params=["ads", "campaigns"])
def getter(request, monkeypatch):
    if request.param == "ads":
        module, sdk_class, factory = ads, Ad, "get_ad"
        fields = ads.AD_DETAIL_FIELDS
    else:
        module, sdk_class, factory = campaigns, Campaign, "get_campaign"
        fields = campaigns.CAMPAIGN_DETAIL_FIELDS

    # Authentication is never initialized; no credential values are needed.
    client = MetaSDKClient(MetaCredentials.model_construct())
    initialize = Mock()
    node = Mock(spec=sdk_class)
    lookup = Mock(return_value=node)
    monkeypatch.setattr(client, "initialize", initialize)
    monkeypatch.setattr(client, factory, lookup)
    monkeypatch.setattr(module, "build_client", lambda auth_config: client)
    return request.param, module, sdk_class, fields, node, lookup, initialize


def test_detail_fields_are_supported_and_object_specific(getter):
    command, _, sdk_class, fields, *_ = getter
    assert len(fields) == len(set(fields))
    assert set(fields) <= set(sdk_class._field_types)
    assert {
        "account_id", "id", "name", "status", "configured_status", "effective_status", "adlabels"
    } <= set(fields)
    if command == "ads":
        assert {"adset_id", "campaign_id", "creative", "ad_review_feedback"} <= set(fields)
        assert not {"daily_budget", "lifetime_budget", "budget_remaining"} & set(fields)
    else:
        assert {"daily_budget", "lifetime_budget", "budget_remaining", "objective"} <= set(fields)
        assert not {"adset_id", "campaign_id", "creative", "ad_review_feedback"} & set(fields)


@pytest.mark.parametrize("response_kind", ["sdk_object", "dict"])
@pytest.mark.parametrize("optional_state", ["populated", "empty", "null", "omitted"])
def test_get_serializes_sdk_verification_fields_without_changing_shape(
    getter, optional_state, response_kind
):
    command, _, sdk_class, fields, node, lookup, initialize = getter
    payload = {
        "id": "123",
        "account_id": "456",
        "name": "Verification object",
        "status": "ARCHIVED" if command == "ads" else "PAUSED",
        "configured_status": "ARCHIVED" if command == "ads" else "PAUSED",
        "effective_status": "ARCHIVED" if command == "ads" else "PAUSED",
    }
    if command == "ads":
        payload.update(adset_id="789", campaign_id="987", creative={"id": "654"})
    else:
        payload["objective"] = "OUTCOME_LEADS"

    if optional_state != "omitted":
        payload["adlabels"] = (
            [{"id": "321", "name": "Winner"}] if optional_state == "populated"
            else [] if optional_state == "empty" else None
        )
        if command == "campaigns":
            payload.update(
                daily_budget="1000" if optional_state == "populated" else None,
                lifetime_budget="5000" if optional_state == "empty" else None,
                budget_remaining="0" if optional_state == "empty" else None,
            )

    # Exercise the real SDK export path, including nested label objects, with a mocked GET.
    result_object = sdk_class()
    result_object.update(payload)
    if optional_state == "populated":
        label = AdLabel()
        label.update(payload["adlabels"][0])
        result_object["adlabels"] = [label]
    node.api_get.return_value = result_object if response_kind == "sdk_object" else payload
    # The official SDK drops None values during export; dict responses preserve explicit nulls.
    expected = (
        {key: value for key, value in payload.items() if value is not None}
        if response_kind == "sdk_object" else payload
    )

    result = runner.invoke(app, [command, "get", "123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    initialize.assert_called_once_with()
    lookup.assert_called_once_with("123")
    node.api_get.assert_called_once_with(fields=fields)
    assert node.method_calls == [("api_get", (), {"fields": fields})]


@pytest.mark.parametrize("optional_fields_present", [False, True])
def test_get_human_table_includes_verification_fields_and_handles_absence(
    getter, monkeypatch, optional_fields_present
):
    command, module, sdk_class, fields, node, *_ = getter
    payload = {"id": "123"}
    if optional_fields_present:
        payload.update(account_id="456", adlabels=[{"id": "321", "name": "Winner"}])
    result_object = sdk_class()
    result_object.update(payload)
    node.api_get.return_value = result_object
    table = Mock()
    monkeypatch.setattr(module, "print_table", table)

    result = runner.invoke(app, [command, "get", "123"])

    assert result.exit_code == 0, result.output
    table.assert_called_once_with(
        f"{'Ad' if command == 'ads' else 'Campaign'} 123",
        ["Field", "Value"],
        [[field, payload.get(field)] for field in fields],
        False,
    )
    node.api_get.assert_called_once_with(fields=fields)

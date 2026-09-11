from __future__ import annotations

import json
from copy import deepcopy
from unittest.mock import Mock, call

import pytest
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.campaign import Campaign
from sdk_mutation_stub import PendingMutationMock
from test_sdk_pagination import PreloadedCursor
from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.commands.object_labels import OBJECT_LABEL_FIELDS
from meta_cli.config import MetaCredentials
from meta_cli.exceptions import APIError
from meta_cli.sdk import MetaSDKClient

runner = CliRunner()
TOKEN = "SYNTHETIC_OBJECT_LABEL_TOKEN"
SECRET = "SYNTHETIC_OBJECT_LABEL_SECRET"
LABEL = {"id": "901", "name": "Winner"}
OTHER = {"id": "902", "name": "Other"}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(tmp_path / "absent.yaml"))
    monkeypatch.delenv("META_CLI_ENVIRONMENT", raising=False)
    monkeypatch.setenv("LIVE_META_TESTS", "0")
    monkeypatch.setattr("facebook_business.api.FacebookAdsApi.call",
                        Mock(side_effect=AssertionError("Live API forbidden")))


@pytest.fixture(params=["ad", "campaign"])
def sdk(request, monkeypatch):
    kind = request.param
    client = MetaSDKClient(MetaCredentials.model_validate({
        "META_ACCESS_TOKEN": TOKEN, "META_APP_ID": "101",
        "META_APP_SECRET": SECRET, "META_AD_ACCOUNT_ID": "act_123",
    }), active_environment="test-account")
    account = Mock()
    account.api_get.return_value = {"id": "act_123"}
    account.get_ad_labels.return_value = [LABEL, OTHER]
    state = {
        "id": "100", "account_id": "123", "name": "Target", "adlabels": [OTHER],
        "status": "PAUSED", "effective_status": "PAUSED", "daily_budget": "1000",
        "targeting": {"geo_locations": {"countries": ["IN"]}},
        "adset_id": "200", "campaign_id": "300",
    }
    target = Mock()
    target.api_get = PendingMutationMock(
        Ad if kind == "ad" else Campaign, object_id="100",
        side_effect=lambda **kwargs: deepcopy(state),
    )

    def add(**kwargs):
        state["adlabels"].append(LABEL)
        return {"success": True}

    target.create_ad_label = PendingMutationMock(Ad if kind == "ad" else Campaign, side_effect=add)
    constructor = Mock(return_value=target)
    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_ad_account", lambda: account)
    monkeypatch.setattr(client, f"get_{kind}", constructor)
    monkeypatch.setattr(client, "get_campaign" if kind == "ad" else "get_ad",
                        Mock(side_effect=AssertionError("Wrong object type")))
    monkeypatch.setattr(f"meta_cli.commands.{kind}s.build_client", lambda auth: client)
    return kind, client, account, target, state, constructor


def invoke(sdk, *flags, input=None, object_id="100", label_id="901"):
    return runner.invoke(app, [sdk[0] + "s", "add-label", object_id,
                              "--label-id", label_id, "--json", *flags], input=input)


def output(result):
    return json.loads(result.output[result.output.index("{"):])


def assert_zero_writes(sdk):
    _, _, account, target, _, _ = sdk
    assert all(c[0] in {"api_get", "get_ad_labels"} for c in account.mock_calls)
    assert all(c[0] in {"api_get", "api_get().export_all_data"} for c in target.mock_calls)


@pytest.mark.parametrize("flags,input", [(["--yes"], None), (["-y"], None), ([], "y\n")])
def test_add_exact_sdk_edge_payload_and_readback_preserves_everything(sdk, flags, input):
    kind, _, account, target, state, constructor = sdk
    before = deepcopy(state)
    result = invoke(sdk, *flags, input=input)
    assert result.exit_code == 0, result.output
    data = output(result)
    assert data["operation"] == f"{kind}_add_label"
    assert data["environment"] == "test-account" and data["account_id"] == "act_123"
    assert data["outcome"] == "added" and data["changed"] and data["verified"]
    assert data["before_label_ids"] == ["902"]
    assert data["after_label_ids"] == ["902", "901"]
    assert data["mutation"] == {"adlabels": [{"id": "901"}]}
    assert target.mock_calls == [
        call.api_get(fields=OBJECT_LABEL_FIELDS, pending=True),
        call.create_ad_label(params={"adlabels": [{"id": "901"}]}, pending=True),
        call.api_get(fields=OBJECT_LABEL_FIELDS, pending=True),
    ]
    assert constructor.call_args_list == [call("100")] * 3
    assert account.mock_calls == [call.api_get(fields=["id"]),
                                  call.get_ad_labels(fields=["id", "name"], params={"limit": 50})]
    assert state == {**before, "adlabels": [OTHER, LABEL]}
    if not flags:
        assert "test-account / act_123" in result.output


@pytest.mark.parametrize("flags", [["--dry-run"], ["--dry-run", "--yes"]])
def test_dry_run_no_prompt_zero_writes(sdk, flags):
    result = invoke(sdk, *flags)
    assert result.exit_code == 0, result.output
    assert output(result)["outcome"] == "would_add"
    assert output(result)["changed"] is False
    assert_zero_writes(sdk)


@pytest.mark.parametrize("flags", [[], ["--yes"], ["--dry-run"]])
def test_existing_label_noop_even_without_confirmation(sdk, flags):
    sdk[4]["adlabels"].append(LABEL)
    result = invoke(sdk, *flags)
    assert result.exit_code == 0, result.output
    assert output(result)["outcome"] == "already_applied"
    assert output(result)["changed"] is False
    assert_zero_writes(sdk)


def test_repeated_application_never_duplicates(sdk):
    assert invoke(sdk, "--yes").exit_code == 0
    result = invoke(sdk)
    assert result.exit_code == 0 and output(result)["outcome"] == "already_applied"
    assert sdk[3].create_ad_label.call_count == 1
    assert sdk[4]["adlabels"] == [OTHER, LABEL]


@pytest.mark.parametrize("input", ["n\n", ""])
def test_decline_or_abort_zero_writes(sdk, input):
    assert invoke(sdk, input=input).exit_code == 1
    assert_zero_writes(sdk)


@pytest.mark.parametrize("field,value", [
    ("id", None), ("id", "999"), ("account_id", "999"), ("account_id", None),
    ("account_id", "invalid"), ("adlabels", None), ("adlabels", {}),
    ("adlabels", {"data": [OTHER], "paging": {"next": "more"}}),
    ("adlabels", [None]), ("adlabels", [{}]), ("adlabels", [{"id": "invalid"}]),
    ("adlabels", [OTHER, OTHER]),
])
def test_bad_target_fails_closed_even_dry_run(sdk, field, value):
    sdk[4][field] = value
    result = invoke(sdk, "--dry-run", "--yes")
    assert result.exit_code == 1, result.output
    assert output(result)["ok"] is False
    assert_zero_writes(sdk)


def test_missing_target_fails_without_edge_lookup(sdk, monkeypatch):
    edge = Mock(side_effect=AssertionError("Missing target must not resolve labels"))
    monkeypatch.setattr(sdk[1], "list_object_labels", edge)
    sdk[3].api_get.side_effect = None
    sdk[3].api_get.return_value = {}
    assert invoke(sdk, "--yes").exit_code == 1
    edge.assert_not_called()
    assert_zero_writes(sdk)


def test_missing_label_field_requires_successful_edge_lookup(sdk, monkeypatch):
    del sdk[4]["adlabels"]
    edge = Mock(side_effect=APIError("Incomplete target label edge"))
    monkeypatch.setattr(sdk[1], "list_object_labels", edge)
    result = invoke(sdk, "--yes")
    assert result.exit_code == 1
    assert "Incomplete target label edge" in output(result)["error"]
    edge.assert_called_once_with(sdk[0], "100")
    sdk[2].get_ad_labels.assert_not_called()
    assert_zero_writes(sdk)


@pytest.mark.parametrize("rows", [[], [OTHER], [LABEL, LABEL], [{"id": "901"}]])
def test_missing_foreign_or_invalid_label_inventory_fails(sdk, rows):
    # Label absence in full configured-account inventory includes foreign labels.
    sdk[2].get_ad_labels.return_value = rows
    assert invoke(sdk, "--yes").exit_code == 1
    assert_zero_writes(sdk)


def test_label_membership_reads_every_page(sdk):
    sdk[2].get_ad_labels.return_value = PreloadedCursor([OTHER], [[LABEL]])
    assert invoke(sdk, "--yes").exit_code == 0
    sdk[3].create_ad_label.assert_called_once_with(
        params={"adlabels": [{"id": "901"}]}, pending=True,
    )


@pytest.mark.parametrize("account_id", [None, "act_999", "invalid"])
def test_configured_account_lookup_mismatch(sdk, account_id):
    sdk[2].api_get.return_value = {"id": account_id}
    assert invoke(sdk, "--yes").exit_code == 1
    assert_zero_writes(sdk)
    sdk[3].api_get.assert_not_called()


@pytest.mark.parametrize("kwargs", [{"object_id": "bad"}, {"label_id": ""},
                                     {"label_id": "９０１"}, {"object_id": "act_100"}])
def test_invalid_ids_before_reads(sdk, kwargs):
    assert invoke(sdk, "--yes", **kwargs).exit_code == 1
    assert not sdk[2].mock_calls and not sdk[3].mock_calls


@pytest.mark.parametrize("response", [None, False, {"success": False},
                                       {"success": False, "id": "100"}, {"id": "999"},
                                       {"success": True, "id": "999"}])
def test_negative_or_unknown_acknowledgement_no_retry(sdk, response):
    sdk[3].create_ad_label.side_effect = None
    sdk[3].create_ad_label.return_value = response
    result = invoke(sdk, "--yes")
    assert result.exit_code == 1, result.output
    assert "before retrying" in output(result)["error"]
    assert sdk[3].create_ad_label.call_count == 1
    assert sdk[3].api_get.call_count == 1


def test_sdk_object_response_supported_with_readback(sdk):
    def add(**kwargs):
        sdk[4]["adlabels"].append(LABEL)
        return Mock(export_all_data=lambda: {"id": "100"})
    sdk[3].create_ad_label.side_effect = add
    assert invoke(sdk, "--yes").exit_code == 0


@pytest.mark.parametrize("after", [[OTHER], [LABEL], None])
def test_readback_failure_reports_possible_write_no_rollback(sdk, after):
    def add(**kwargs):
        sdk[4]["adlabels"] = after
        return {"success": True}
    sdk[3].create_ad_label.side_effect = add
    result = invoke(sdk, "--yes")
    assert result.exit_code == 1
    assert "may have succeeded" in output(result)["error"]
    assert sdk[3].create_ad_label.call_count == 1
    assert all(c[0] in {"api_get", "create_ad_label"} for c in sdk[3].mock_calls)


def test_explicit_empty_labels_supported(sdk):
    sdk[4]["adlabels"] = []
    result = invoke(sdk, "--yes")
    assert result.exit_code == 0, result.output
    assert output(result)["before_label_ids"] == []
    assert output(result)["after_label_ids"] == ["901"]
    sdk[3].create_ad_label.assert_called_once_with(
        params={"adlabels": [{"id": "901"}]}, pending=True,
    )


def test_readback_accepts_concurrent_addition(sdk):
    def add(**kwargs):
        sdk[4]["adlabels"].extend([LABEL, {"id": "903"}])
        return {"success": True}
    sdk[3].create_ad_label.side_effect = add
    assert invoke(sdk, "--yes").exit_code == 0


@pytest.mark.parametrize("stage", ["account", "target", "labels", "write", "readback", "export"])
def test_errors_redacted(sdk, stage):
    error = RuntimeError(f"Synthetic failure {TOKEN} {SECRET}")
    if stage == "account":
        sdk[2].api_get.side_effect = error
    elif stage == "target":
        sdk[3].api_get.side_effect = error
    elif stage == "labels":
        sdk[2].get_ad_labels.side_effect = error
    elif stage == "write":
        sdk[3].create_ad_label.side_effect = error
    elif stage == "export":
        sdk[3].api_get.side_effect = None
        sdk[3].api_get.return_value = Mock(export_all_data=Mock(side_effect=error))
    else:
        sdk[3].api_get.side_effect = [deepcopy(sdk[4]), error]
    result = invoke(sdk, "--yes")
    assert result.exit_code == 1, result.output
    assert TOKEN not in result.output and SECRET not in result.output
    assert "[REDACTED]" in output(result)["error"]
    if stage not in {"write", "readback"}:
        assert_zero_writes(sdk)


@pytest.mark.parametrize("kind", ["ad", "campaign"])
def test_help_and_missing_required_arguments_offline(kind):
    result = runner.invoke(app, [kind + "s", "add-label", "--help"])
    assert result.exit_code == 0
    for flag in ("--label-id", "--dry-run", "--yes"):
        assert flag in result.output
    assert runner.invoke(app, [kind + "s", "add-label", "100"]).exit_code == 2
    assert runner.invoke(app, [kind + "s", "add-label", "100", "--label-id", "901",
                               "--dry-run"]).exit_code == 1


@pytest.mark.parametrize("kind", ["ad", "campaign"])
def test_process_environment_routing_does_not_persist(kind, tmp_path, monkeypatch):
    path = tmp_path / "environments.yaml"
    contents = """active_profile: first
profiles:
  first:
    access_token: synthetic-first-token
    app_id: '1'
    app_secret: synthetic-first-secret
    ad_account_id: act_123
  second:
    access_token: synthetic-second-token
    app_id: '2'
    app_secret: synthetic-second-secret
    ad_account_id: act_456
"""
    path.write_text(contents)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(path))
    monkeypatch.setenv("META_CLI_ENVIRONMENT", "second")
    account = Mock()
    account.api_get.return_value = {"id": "act_456"}
    account.get_ad_labels.return_value = [LABEL]
    target = Mock()
    before = {"id": "100", "account_id": "456", "adlabels": []}
    target.api_get = PendingMutationMock(
        Ad if kind == "ad" else Campaign, object_id="100",
        side_effect=[before, {**before, "adlabels": [LABEL]}],
    )
    target.create_ad_label = PendingMutationMock(
        Ad if kind == "ad" else Campaign, return_value={"success": True},
    )
    account_constructor = Mock(return_value=account)
    monkeypatch.setattr(MetaSDKClient, "initialize", lambda self: None)
    monkeypatch.setattr(MetaSDKClient, "_core_imports", lambda self: (None, account_constructor))
    target_constructor = Mock(return_value=target)
    monkeypatch.setattr(MetaSDKClient, f"get_{kind}", target_constructor)
    result = runner.invoke(app, [kind + "s", "add-label", "100", "--label-id", "901",
                               "--yes", "--json"])
    assert result.exit_code == 0, result.output
    assert output(result)["environment"] == "second"
    assert output(result)["account_id"] == "act_456"
    assert account_constructor.call_args_list == [call("act_456")] * 2
    assert target_constructor.call_args_list == [call("100")] * 3
    target.create_ad_label.assert_called_once_with(
        params={"adlabels": [{"id": "901"}]}, pending=True,
    )
    assert path.read_text() == contents

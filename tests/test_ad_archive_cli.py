from __future__ import annotations

import json
from copy import deepcopy
from unittest.mock import Mock, call

import pytest
from facebook_business.adobjects.ad import Ad
from sdk_mutation_stub import PendingMutationMock
from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.commands.ad_archiving import ARCHIVE_FIELDS, NON_DELIVERING_EFFECTIVE_STATUSES
from meta_cli.config import MetaCredentials
from meta_cli.sdk import MetaSDKClient

runner = CliRunner()
TOKEN = "SYNTHETIC_ARCHIVE_TOKEN"
SECRET = "SYNTHETIC_ARCHIVE_SECRET"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(tmp_path / "absent.yaml"))
    monkeypatch.delenv("META_CLI_ENVIRONMENT", raising=False)
    monkeypatch.setenv("LIVE_META_TESTS", "0")
    monkeypatch.setattr("facebook_business.api.FacebookAdsApi.call",
                        Mock(side_effect=AssertionError("Live API forbidden")))


@pytest.fixture
def sdk(monkeypatch):
    client = MetaSDKClient(MetaCredentials.model_validate({
        "META_ACCESS_TOKEN": TOKEN, "META_APP_ID": "101",
        "META_APP_SECRET": SECRET, "META_AD_ACCOUNT_ID": "act_123",
    }), active_environment="test-account")
    account = Mock()
    account.api_get.return_value = {"id": "act_123"}
    state = {
        "id": "100", "account_id": "123", "name": "Target", "adlabels": [{"id": "901"}],
        "status": "PAUSED", "configured_status": "PAUSED", "effective_status": "PAUSED",
        "adset_id": "200", "campaign_id": "300", "creative": {"id": "400"},
        "targeting": {"geo_locations": {"countries": ["IN"]}}, "daily_budget": "1000",
    }
    ad = Mock()
    ad.api_get.side_effect = lambda **kwargs: deepcopy(state)

    def update(**kwargs):
        assert kwargs == {"params": {"status": "ARCHIVED"}, "pending": True}
        for field in ("status", "configured_status", "effective_status"):
            state[field] = "ARCHIVED"
        return {"success": True}

    ad.api_update = PendingMutationMock(Ad, object_id="100", side_effect=update)
    constructor = Mock(return_value=ad)
    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_ad_account", lambda: account)
    monkeypatch.setattr(client, "get_ad", constructor)
    for method in ("get_campaign", "get_adset"):
        monkeypatch.setattr(client, method, Mock(side_effect=AssertionError("No parent access")))
    monkeypatch.setattr("meta_cli.commands.ads.build_client", lambda auth: client)
    return client, account, ad, state, constructor


def invoke(*flags, input=None, ad_id="100"):
    return runner.invoke(app, ["ads", "archive", ad_id, "--json", *flags], input=input)


def output(result):
    return json.loads(result.output[result.output.index("{"):])


def assert_zero_writes(sdk):
    assert all(c[0] in {"api_get", "api_get().export_all_data"} for c in sdk[1].mock_calls)
    assert all(c[0] in {"api_get", "api_get().export_all_data"} for c in sdk[2].mock_calls)
    sdk[0].get_campaign.assert_not_called()
    sdk[0].get_adset.assert_not_called()


@pytest.mark.parametrize("configured", ["ACTIVE", "PAUSED"])
@pytest.mark.parametrize("effective", sorted(NON_DELIVERING_EFFECTIVE_STATUSES))
def test_non_delivering_states_only_selected_ad_status_updated(sdk, configured, effective):
    client, account, ad, state, constructor = sdk
    state.update(status=configured, configured_status=configured, effective_status=effective)
    before = deepcopy(state)
    result = invoke("--yes")
    assert result.exit_code == 0, result.output
    data = output(result)
    assert data["operation"] == "ad_archive"
    assert data["environment"] == "test-account" and data["account_id"] == "act_123"
    assert data["ad_id"] == "100"
    assert data["outcome"] == "archived" and data["changed"] and data["verified"]
    assert data["dry_run"] is False
    assert data["before"]["configured_status"] == configured
    assert data["before"]["effective_status"] == effective
    assert data["after"]["configured_status"] == data["after"]["effective_status"] == "ARCHIVED"
    assert data["mutation"] == {"status": "ARCHIVED"}
    assert ad.mock_calls == [call.api_get(fields=ARCHIVE_FIELDS),
                             call.api_update(params={"status": "ARCHIVED"}, pending=True),
                             call.api_get(fields=ARCHIVE_FIELDS)]
    assert constructor.call_args_list == [call("100")] * 3
    assert account.mock_calls == [call.api_get(fields=["id"])]
    assert state == {**before, "status": "ARCHIVED", "configured_status": "ARCHIVED",
                     "effective_status": "ARCHIVED"}
    client.get_campaign.assert_not_called()
    client.get_adset.assert_not_called()


@pytest.mark.parametrize("flags", [["--dry-run"], ["--dry-run", "--yes"]])
def test_dry_run_reads_but_no_prompt_or_writes(sdk, flags):
    result = invoke(*flags)
    assert result.exit_code == 0, result.output
    data = output(result)
    assert data["outcome"] == "would_archive" and data["dry_run"]
    assert data["changed"] is False and "verified" not in data
    assert data["mutation"] == {"status": "ARCHIVED"}
    sdk[2].api_get.assert_called_once_with(fields=ARCHIVE_FIELDS)
    assert_zero_writes(sdk)


@pytest.mark.parametrize("flags", [[], ["--yes"], ["--dry-run"]])
def test_already_archived_noop_without_prompt(sdk, flags):
    sdk[3].update(status="ARCHIVED", configured_status="ARCHIVED", effective_status="ARCHIVED")
    result = invoke(*flags)
    assert result.exit_code == 0, result.output
    assert output(result)["outcome"] == "already_archived"
    assert output(result)["changed"] is False
    assert_zero_writes(sdk)


def test_repeated_archive_is_idempotent(sdk):
    assert invoke("--yes").exit_code == 0
    result = invoke()
    assert result.exit_code == 0 and output(result)["outcome"] == "already_archived"
    sdk[2].api_update.assert_called_once_with(params={"status": "ARCHIVED"}, pending=True)


@pytest.mark.parametrize("flags,input", [([], "y\n"), (["-y"], None)])
def test_confirmed_writes_and_short_yes_flag(sdk, flags, input):
    result = invoke(*flags, input=input)
    assert result.exit_code == 0, result.output
    sdk[2].api_update.assert_called_once_with(params={"status": "ARCHIVED"}, pending=True)
    if not flags:
        assert "test-account / act_123" in result.output
        assert "no deletion or parent changes" in result.output


@pytest.mark.parametrize("input", ["n\n", ""])
def test_decline_or_abort_no_write(sdk, input):
    assert invoke(input=input).exit_code == 1
    assert_zero_writes(sdk)


@pytest.mark.parametrize("configured,effective", [
    ("ACTIVE", "ACTIVE"), ("PAUSED", "ACTIVE"), ("ACTIVE", "WITH_ISSUES"),
    ("PAUSED", "WITH_ISSUES"), ("DELETED", "DELETED"), ("PAUSED", "DELETED"),
    ("ARCHIVED", "PAUSED"), ("ACTIVE", "ARCHIVED"), ("UNKNOWN", "PAUSED"),
    ("PAUSED", "UNKNOWN"), ("DISAPPROVED", "DISAPPROVED"),
])
@pytest.mark.parametrize("flags", [["--yes"], ["--dry-run"]])
def test_unsupported_states_fail_closed(sdk, configured, effective, flags):
    sdk[3].update(status=configured, configured_status=configured, effective_status=effective)
    result = invoke(*flags)
    assert result.exit_code == 1, result.output
    assert "Unsupported ad state" in output(result)["error"]
    assert_zero_writes(sdk)


@pytest.mark.parametrize("field,value", [
    ("id", None), ("id", "999"), ("id", "bad"), ("account_id", None),
    ("account_id", "999"), ("account_id", "bad"), ("adset_id", None),
    ("campaign_id", "bad"), ("status", None), ("configured_status", None),
    ("effective_status", None), ("effective_status", []), ("effective_status", {}),
    ("configured_status", "ACTIVE"), ("status", "ACTIVE"),
])
def test_invalid_targets_and_inconsistent_statuses_even_dry_run(sdk, field, value):
    sdk[3][field] = value
    result = invoke("--dry-run", "--yes")
    assert result.exit_code == 1, result.output
    assert output(result)["ok"] is False
    assert_zero_writes(sdk)


@pytest.mark.parametrize("field", ["id", "account_id", "status", "configured_status",
                                   "effective_status", "adset_id", "campaign_id"])
def test_missing_required_field_no_write(sdk, field):
    del sdk[3][field]
    assert invoke("--yes").exit_code == 1
    assert_zero_writes(sdk)


@pytest.mark.parametrize("target", [None, {}, []])
def test_missing_or_malformed_ad(sdk, target):
    sdk[2].api_get.side_effect = None
    sdk[2].api_get.return_value = target
    assert invoke("--yes").exit_code == 1
    assert_zero_writes(sdk)


@pytest.mark.parametrize("account", [None, {}, [], {"id": "act_999"}, {"id": "bad"}])
def test_invalid_account_before_ad_lookup(sdk, account):
    sdk[1].api_get.return_value = account
    assert invoke("--yes").exit_code == 1
    sdk[2].api_get.assert_not_called()
    assert_zero_writes(sdk)


@pytest.mark.parametrize("ad_id", ["bad", "", "１００", "act_100", "100/ads"])
def test_invalid_input_id_before_any_reads(sdk, ad_id):
    assert invoke("--yes", ad_id=ad_id).exit_code == 1
    assert not sdk[1].mock_calls and not sdk[2].mock_calls


@pytest.mark.parametrize("response", [None, False, {}, {"success": False},
                                       {"success": False, "id": "100"}, {"id": "999"},
                                       {"success": True, "id": "999"}])
def test_bad_write_acknowledgement_no_retry_or_rollback(sdk, response):
    sdk[2].api_update.side_effect = None
    sdk[2].api_update.return_value = response
    result = invoke("--yes")
    assert result.exit_code == 1, result.output
    assert "unconfirmed" in output(result)["error"]
    assert "before retrying" in output(result)["error"]
    assert sdk[2].api_get.call_count == 1
    sdk[2].api_update.assert_called_once_with(params={"status": "ARCHIVED"}, pending=True)
    assert all(c[0] in {"api_get", "api_update"} for c in sdk[2].mock_calls)


def test_sdk_object_acknowledgement_with_readback(sdk):
    original = sdk[2].api_update.side_effect

    def update(**kwargs):
        original(**kwargs)
        return Mock(export_all_data=lambda: {"id": "100"})

    sdk[2].api_update.side_effect = update
    assert invoke("--yes").exit_code == 0


@pytest.mark.parametrize("field,value", [
    ("id", "999"), ("account_id", "999"), ("adset_id", "999"), ("campaign_id", "999"),
    ("status", "PAUSED"), ("configured_status", "ACTIVE"), ("effective_status", "PAUSED"),
    ("configured_status", None),
])
def test_failed_readback_reports_possible_write(sdk, field, value):
    original = sdk[2].api_update.side_effect

    def update(**kwargs):
        result = original(**kwargs)
        sdk[3][field] = value
        return result

    sdk[2].api_update.side_effect = update
    result = invoke("--yes")
    assert result.exit_code == 1, result.output
    assert "may have succeeded, but verification failed" in output(result)["error"]
    assert sdk[2].api_get.call_count == 2
    sdk[2].api_update.assert_called_once_with(params={"status": "ARCHIVED"}, pending=True)
    assert all(c[0] in {"api_get", "api_update"} for c in sdk[2].mock_calls)


@pytest.mark.parametrize("stage", ["account", "account_export", "target", "target_export",
                                    "write", "write_export", "readback", "constructor"])
def test_sdk_failures_redacted_and_never_retried(sdk, stage):
    error = RuntimeError(f"Synthetic failure {TOKEN} {SECRET}")
    bad_export = Mock(export_all_data=Mock(side_effect=error))
    if stage == "account":
        sdk[1].api_get.side_effect = error
    elif stage == "account_export":
        sdk[1].api_get.return_value = bad_export
    elif stage == "target":
        sdk[2].api_get.side_effect = error
    elif stage == "target_export":
        sdk[2].api_get.side_effect = [bad_export]
    elif stage == "write":
        sdk[2].api_update.side_effect = error
    elif stage == "write_export":
        sdk[2].api_update.side_effect = [bad_export]
    elif stage == "constructor":
        sdk[4].side_effect = error
    else:
        sdk[2].api_get.side_effect = [deepcopy(sdk[3]), error]
    result = invoke("--yes")
    assert result.exit_code == 1, result.output
    assert TOKEN not in result.output and SECRET not in result.output
    assert "[REDACTED]" in output(result)["error"]
    if stage not in {"write", "write_export", "readback"}:
        assert_zero_writes(sdk)
    else:
        sdk[2].api_update.assert_called_once_with(params={"status": "ARCHIVED"}, pending=True)
        assert "before retrying" in output(result)["error"]


def test_help_missing_args_and_missing_environment_offline():
    result = runner.invoke(app, ["ads", "archive", "--help"])
    assert result.exit_code == 0
    for flag in ("--dry-run", "--yes", "--json"):
        assert flag in result.output
    assert runner.invoke(app, ["ads", "archive"]).exit_code == 2
    assert invoke("--dry-run").exit_code == 1


@pytest.mark.parametrize("dry_run", [False, True])
def test_process_environment_override_is_bound_and_not_persisted(tmp_path, monkeypatch, dry_run):
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
    ad = Mock()
    before = {"id": "100", "account_id": "456", "status": "ACTIVE",
              "configured_status": "ACTIVE", "effective_status": "CAMPAIGN_PAUSED",
              "adset_id": "200", "campaign_id": "300"}
    after = {**before, "status": "ARCHIVED", "configured_status": "ARCHIVED",
             "effective_status": "ARCHIVED"}
    ad.api_get.side_effect = [before, after]
    ad.api_update = PendingMutationMock(Ad, object_id="100", return_value={"success": True})
    account_constructor = Mock(return_value=account)
    ad_constructor = Mock(return_value=ad)
    monkeypatch.setattr(MetaSDKClient, "initialize", lambda self: None)
    monkeypatch.setattr(MetaSDKClient, "_core_imports", lambda self: (None, account_constructor))
    monkeypatch.setattr(MetaSDKClient, "get_ad", ad_constructor)
    result = invoke("--dry-run" if dry_run else "--yes")
    assert result.exit_code == 0, result.output
    assert output(result)["environment"] == "second"
    assert output(result)["account_id"] == "act_456"
    account_constructor.assert_called_once_with("act_456")
    assert ad_constructor.call_args_list == [call("100")] * (1 if dry_run else 3)
    if dry_run:
        ad.api_update.assert_not_called()
    else:
        ad.api_update.assert_called_once_with(params={"status": "ARCHIVED"}, pending=True)
    assert path.read_text() == contents


def test_official_sdk_archive_request_is_node_post_not_delete(monkeypatch):
    from facebook_business.adobjects.ad import Ad
    from facebook_business.api import FacebookRequest

    execute = Mock(side_effect=AssertionError("Request execution forbidden"))
    monkeypatch.setattr(FacebookRequest, "execute", execute)
    request = Ad("100").api_update(params={"status": Ad.Status.archived}, pending=True)
    assert request._node_id == "100"
    assert request._method == "POST" and request._endpoint == ""
    assert request._params == {"status": "ARCHIVED"}
    execute.assert_not_called()

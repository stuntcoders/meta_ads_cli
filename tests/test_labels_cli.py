from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from facebook_business.adobjects.adlabel import AdLabel
from sdk_mutation_stub import PendingMutationMock
from test_sdk_pagination import PreloadedCursor
from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.config import MetaCredentials
from meta_cli.sdk import MetaSDKClient

runner = CliRunner()
LABEL = {"id": "901", "name": "Winner"}
TOKEN = "SYNTHETIC_LABEL_TOKEN_SENTINEL"
SECRET = "SYNTHETIC_LABEL_SECRET_SENTINEL"


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(tmp_path / "absent.yaml"))
    monkeypatch.delenv("META_CLI_ENVIRONMENT", raising=False)
    monkeypatch.setenv("LIVE_META_TESTS", "0")
    monkeypatch.setattr(
        "facebook_business.api.FacebookAdsApi.call",
        Mock(side_effect=AssertionError("Live API access forbidden")),
    )


@pytest.fixture
def sdk(monkeypatch):
    credentials = MetaCredentials.model_validate({
        "META_ACCESS_TOKEN": TOKEN,
        "META_APP_ID": "101",
        "META_APP_SECRET": SECRET,
        "META_AD_ACCOUNT_ID": "act_123",
    })
    client = MetaSDKClient(credentials, active_environment="test-account")
    account = Mock()
    account.api_get.return_value = {"id": "act_123"}
    account.get_ad_labels.return_value = []
    account.create_ad_label = PendingMutationMock(AdLabel, return_value={"id": "901"})
    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_ad_account", lambda: account)
    monkeypatch.setattr("meta_cli.commands.labels.build_client", lambda auth: client)
    return client, account


def invoke_create(*args, input=None):
    return runner.invoke(app, ["labels", "create", "--name", "Winner", "--json", *args], input=input)


def test_list_json_reads_only_and_passes_pagination(sdk):
    _, account = sdk
    account.get_ad_labels.return_value = PreloadedCursor([LABEL], [[{"id": "902", "name": "Other"}]])
    result = runner.invoke(app, ["labels", "list", "--json", "--limit", "10", "--after", "cursor"])
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert [label["id"] for label in output["data"]] == ["901", "902"]
    assert output["paging"]["pages_fetched"] == 2
    assert output["account_id"] == "act_123"
    assert output["environment"] == "test-account"
    account.api_get.assert_called_once_with(fields=["id"])
    account.get_ad_labels.assert_called_once_with(fields=["id", "name"], params={"limit": 10, "after": "cursor"})
    assert [call[0] for call in account.mock_calls] == ["api_get", "get_ad_labels"]


@pytest.mark.parametrize("flags", [["--no-paginate"], ["--max-pages", "1"]])
def test_list_page_cap_and_table(sdk, flags):
    _, account = sdk
    account.get_ad_labels.return_value = PreloadedCursor([LABEL], [[{"id": "902", "name": "Other"}]])
    result = runner.invoke(app, ["labels", "list", *flags])
    assert result.exit_code == 0, result.output
    assert "901" in result.output and "Winner" in result.output
    assert "902" not in result.output
    assert "test-account" in result.output and "act_123" in result.output
    account.create_ad_label.assert_not_called()


def test_list_before_cursor_and_empty_result(sdk):
    _, account = sdk
    result = runner.invoke(app, ["labels", "list", "--before", "previous", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["data"] == []
    account.get_ad_labels.assert_called_once_with(fields=["id", "name"], params={"limit": 50, "before": "previous"})


@pytest.mark.parametrize("flags", [["--after", "a", "--before", "b"], ["--limit", "0"], ["--max-pages", "0"]])
def test_invalid_list_options_do_not_read_or_write(sdk, flags):
    _, account = sdk
    result = runner.invoke(app, ["labels", "list", *flags])
    assert result.exit_code != 0
    assert not account.mock_calls


def test_create_dry_run_reads_no_writes_or_prompt(sdk):
    _, account = sdk
    result = invoke_create("--dry-run")
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert output["outcome"] == "would_create"
    assert output["mutation"] == {"name": "Winner"}
    assert output["dry_run"] is True and output["changed"] is False
    assert [call[0] for call in account.mock_calls] == ["api_get", "get_ad_labels"]


@pytest.mark.parametrize("flags,input", [(["--yes"], None), (["-y"], None), ([], "y\n")])
def test_create_confirmed_name_only_write_and_readback(sdk, flags, input):
    _, account = sdk
    account.get_ad_labels.side_effect = [[], [LABEL]]
    result = invoke_create(*flags, input=input)
    assert result.exit_code == 0, result.output
    # Interactive confirmation precedes JSON; --yes produces pure JSON.
    output = json.loads(result.output[result.output.index("{"):])
    assert output["label"] == LABEL
    assert output["changed"] is True and output["verified"] is True
    assert output["outcome"] == "created"
    account.create_ad_label.assert_called_once_with(params={"name": "Winner"}, pending=True)
    assert [call[0] for call in account.mock_calls] == ["api_get", "get_ad_labels", "create_ad_label", "get_ad_labels"]
    if not flags:
        assert "test-account / act_123" in result.output


@pytest.mark.parametrize("input", ["n\n", ""])
def test_create_declined_or_aborted_does_not_write(sdk, input):
    _, account = sdk
    result = invoke_create(input=input)
    assert result.exit_code == 1
    account.create_ad_label.assert_not_called()


@pytest.mark.parametrize("flags", [[], ["--dry-run"], ["--yes"]])
def test_exact_duplicate_reused_from_later_page_without_prompt(sdk, flags):
    _, account = sdk
    account.get_ad_labels.return_value = PreloadedCursor(
        [{"id": "900", "name": "winner"}], [[LABEL]]
    )
    result = invoke_create(*flags)
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert output["label"] == LABEL and output["outcome"] == "already_exists"
    assert output["changed"] is False
    account.create_ad_label.assert_not_called()


def test_case_sensitive_name_and_whitespace_trimming(sdk):
    _, account = sdk
    account.get_ad_labels.side_effect = [[{"id": "900", "name": "winner"}], [LABEL]]
    result = runner.invoke(app, ["labels", "create", "--name", "  Winner  ", "--yes", "--json"])
    assert result.exit_code == 0, result.output
    account.create_ad_label.assert_called_once_with(params={"name": "Winner"}, pending=True)


def test_ambiguous_duplicate_names_fail_even_dry_run(sdk):
    _, account = sdk
    account.get_ad_labels.return_value = PreloadedCursor([LABEL], [[{"id": "902", "name": "Winner"}]])
    result = invoke_create("--dry-run", "--yes")
    assert result.exit_code == 1
    assert "Multiple account labels" in json.loads(result.output)["error"]
    account.create_ad_label.assert_not_called()


@pytest.mark.parametrize("name", [None, "", "   "])
def test_required_nonblank_name_rejected_before_reads(sdk, name):
    _, account = sdk
    args = ["labels", "create", "--yes"]
    if name is not None:
        args.extend(["--name", name])
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert not account.mock_calls


@pytest.mark.parametrize("account_id", [None, "act_bad", "act_999"])
def test_account_identity_fails_closed(sdk, account_id):
    _, account = sdk
    account.api_get.return_value = {"id": account_id}
    result = invoke_create("--yes")
    assert result.exit_code == 1
    account.get_ad_labels.assert_not_called()
    account.create_ad_label.assert_not_called()


def test_invalid_configured_account_fails_before_reads(sdk):
    client, account = sdk
    client.credentials.ad_account_id = "act_invalid"
    result = invoke_create("--yes")
    assert result.exit_code == 1
    assert not account.mock_calls


@pytest.mark.parametrize("rows", [[{"id": "901"}], [{"id": "bad", "name": "Winner"}], [LABEL, LABEL]])
def test_invalid_label_inventory_blocks_write(sdk, rows):
    _, account = sdk
    account.get_ad_labels.return_value = rows
    result = invoke_create("--yes")
    assert result.exit_code == 1
    account.create_ad_label.assert_not_called()


@pytest.mark.parametrize("response", [False, None, {}, {"success": False}, {"success": False, "id": "901"}, {"id": "bad"}, {"success": True}])
def test_failed_or_unacknowledged_write_not_reported_as_success(sdk, response):
    _, account = sdk
    account.create_ad_label.return_value = response
    result = invoke_create("--yes")
    assert result.exit_code == 1
    output = json.loads(result.output)
    assert output["ok"] is False
    assert "before retrying" in output["error"]
    assert account.create_ad_label.call_count == 1
    assert account.get_ad_labels.call_count == 1


@pytest.mark.parametrize("readback", [[], [{"id": "901", "name": "Unexpected"}]])
def test_readback_mismatch_reports_possible_creation_without_retry(sdk, readback):
    _, account = sdk
    account.get_ad_labels.side_effect = [[], readback]
    result = invoke_create("--yes")
    assert result.exit_code == 1
    error = json.loads(result.output)["error"]
    assert "created label ID 901" in error and "verification failed" in error
    assert account.create_ad_label.call_count == 1


@pytest.mark.parametrize("stage", ["account", "list", "write", "readback", "pagination"])
def test_sdk_failures_redacted_through_cli(sdk, stage):
    _, account = sdk
    error = RuntimeError(f"Synthetic error {TOKEN} {SECRET}")
    if stage == "account":
        account.api_get.side_effect = error
    elif stage == "list":
        account.get_ad_labels.side_effect = error
    elif stage == "pagination":
        cursor = PreloadedCursor([LABEL], [[LABEL]])
        cursor.load_next_page = Mock(side_effect=error)
        account.get_ad_labels.return_value = cursor
    elif stage == "write":
        account.create_ad_label.side_effect = error
    else:
        account.get_ad_labels.side_effect = [[], error]
    result = invoke_create("--yes")
    assert result.exit_code == 1
    assert TOKEN not in result.output and SECRET not in result.output
    assert "[REDACTED]" in result.output
    assert account.create_ad_label.call_count == (1 if stage in {"write", "readback"} else 0)


def test_named_environment_routes_actual_sdk_helpers_without_persisting(tmp_path, monkeypatch):
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
    account.get_ad_labels.side_effect = [[], [LABEL]]
    account.create_ad_label = PendingMutationMock(AdLabel, return_value={"id": "901"})
    account_constructor = Mock(return_value=account)
    monkeypatch.setattr(MetaSDKClient, "initialize", lambda self: None)
    monkeypatch.setattr(MetaSDKClient, "_core_imports", lambda self: (None, account_constructor))
    result = invoke_create("--yes")
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert output["environment"] == "second" and output["account_id"] == "act_456"
    assert all(call.args == ("act_456",) for call in account_constructor.call_args_list)
    assert account_constructor.call_count == 4
    account.create_ad_label.assert_called_once_with(params={"name": "Winner"}, pending=True)
    assert path.read_text() == contents


def test_no_selected_environment_fails_without_sdk(monkeypatch):
    initialize = Mock(side_effect=AssertionError("Must not initialize"))
    monkeypatch.setattr(MetaSDKClient, "initialize", initialize)
    result = invoke_create("--dry-run")
    assert result.exit_code == 1
    assert "No active Meta Ads environment" in result.output
    initialize.assert_not_called()


@pytest.mark.parametrize("command", [["labels", "--help"], ["labels", "list", "--help"], ["labels", "create", "--help"]])
def test_registered_help_is_credential_free(command):
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output

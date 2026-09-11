"""Offline CLI -> configuration -> official SDK -> mocked transport integration.

No CLI service/client/SDK object constructors are replaced. Network access and SDK
crash reporting are blocked; only synthetic temporary environment stores are used.
"""
from __future__ import annotations

import json
import shlex
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from facebook_business.api import FacebookAdsApi, FacebookResponse
from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()
OTHER = {"id": "902", "name": "Other"}
WINNER = {"id": "901", "name": "Winner"}
COMMANDS = [
    ["labels", "list"],
    ["labels", "create", "--name", "Winner"],
    ["ads", "add-label", "100", "--label-id", "901"],
    ["campaigns", "add-label", "300", "--label-id", "901"],
    ["ads", "archive", "100"],
    ["ads", "get", "100"],
    ["campaigns", "get", "300"],
]
MUTATIONS = COMMANDS[1:5]


@pytest.fixture
def transport(tmp_path, monkeypatch):
    profiles = {
        name: {
            "app_id": app_id,
            "access_token": f"synthetic-{name}-token",
            "app_secret": f"synthetic-{name}-secret",
            "ad_account_id": account_id,
            "api_version": "v25.0",
        }
        for name, app_id, account_id in [
            ("first", "1", "act_123"), ("second", "2", "act_456"),
        ]
    }
    path = tmp_path / "environments.yaml"
    path.write_text(yaml.safe_dump({"active_profile": "first", "profiles": profiles}))
    path.chmod(0o600)
    original = path.read_bytes()
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(path))
    monkeypatch.delenv("META_CLI_ENVIRONMENT", raising=False)
    monkeypatch.setenv("LIVE_META_TESTS", "0")
    # Prove normal named routing ignores ambient legacy credential variables.
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "act_999")
    monkeypatch.setenv("META_ACCESS_TOKEN", "synthetic-ignored-ambient-token")
    network = Mock(side_effect=AssertionError("Network access forbidden"))
    monkeypatch.setattr("requests.sessions.Session.request", network)
    monkeypatch.setattr("facebook_business.crashreporter.CrashReporter.enable", lambda: None)
    monkeypatch.setattr(FacebookAdsApi, "_default_api", None)

    states = {}
    for name, profile in profiles.items():
        common = {"account_id": profile["ad_account_id"][4:], "adlabels": [OTHER],
                  "status": "ACTIVE", "configured_status": "ACTIVE"}
        states[name] = {
            "labels": [deepcopy(OTHER)],
            "100": {**deepcopy(common), "id": "100", "name": "Selected ad",
                    "effective_status": "CAMPAIGN_PAUSED", "campaign_id": "300",
                    "adset_id": "200", "creative": {"id": "500"}},
            "300": {**deepcopy(common), "id": "300", "name": "Selected campaign",
                    "status": "PAUSED", "configured_status": "PAUSED",
                    "effective_status": "PAUSED", "daily_budget": "1000",
                    "lifetime_budget": "0", "budget_remaining": "800"},
        }
    calls = []
    failures = {}

    def call(api, method, path, params=None, **kwargs):
        # Assert the real SDK session uses the selected profile, not just its ID.
        name = {"1": "first", "2": "second"}[api._session.app_id]
        profile = profiles[name]
        assert api._session.access_token == profile["access_token"]
        assert api._session.app_secret == profile["app_secret"]
        assert api._api_version == profile["api_version"]
        node, edge = path
        params = deepcopy(params or {})
        calls.append((name, method, node, edge, params))
        if method in failures:
            raise RuntimeError(f"Synthetic transport failure {profile['access_token']} "
                               f"{profile['app_secret']}")
        state = states[name]
        if method == "GET" and node == profile["ad_account_id"] and not edge:
            body = {"id": node}
        elif method == "GET" and node == profile["ad_account_id"] and edge == "adlabels":
            body = {"data": deepcopy(state["labels"])}
        elif method == "GET" and node in {"100", "300"} and not edge:
            fields = params["fields"].split(",")
            body = {key: deepcopy(value) for key, value in state[node].items() if key in fields}
        elif method == "GET" and node in {"100", "300"} and edge == "adlabels":
            assert params["fields"] == "id,name" and set(params) <= {"fields", "after"}
            body = {"data": deepcopy(state[node]["adlabels"])}
        elif method == "POST" and node == profile["ad_account_id"] and edge == "adlabels":
            assert params == {"name": "Winner"}
            state["labels"].append(deepcopy(WINNER))
            body = {"id": "901"}
        elif method == "POST" and node in {"100", "300"} and edge == "adlabels":
            assert params == {"adlabels": [{"id": "901"}]}
            state[node]["adlabels"].append(deepcopy(WINNER))
            body = {"success": True}
        elif method == "POST" and node == "100" and not edge:
            assert params == {"status": "ARCHIVED"}
            for field in ("status", "configured_status", "effective_status"):
                state[node][field] = "ARCHIVED"
            body = {"id": "100"}
        else:
            pytest.fail(f"Unexpected SDK operation: {method} {node}/{edge}")
        return FacebookResponse(body=json.dumps(body), http_status=200, headers={})

    monkeypatch.setattr(FacebookAdsApi, "call", call)
    yield states, calls, failures
    # No command, including errors, may persist the process-local override.
    assert path.read_bytes() == original
    assert path.stat().st_mode & 0o777 == 0o600
    network.assert_not_called()


def invoke(args, **kwargs):
    result = runner.invoke(app, [*args, "--json"], **kwargs)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def writes(calls):
    return [call for call in calls if call[1] != "GET"]


def documented_commands():
    text = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    section = text.split("### Account labels\n", 1)[1].split("### Targeting discovery\n", 1)[0]
    replacements = {"<environment_name>": "second", "<ad_id>": "100",
                    "<campaign_id>": "300", "<label_id>": "901"}
    for line in section.splitlines():
        if not line.startswith("META_CLI_ENVIRONMENT="):
            continue
        for placeholder, value in replacements.items():
            line = line.replace(placeholder, value)
        assignment, executable, *args = shlex.split(line)
        assert assignment == "META_CLI_ENVIRONMENT=second" and executable == "meta-cli"
        assert "--json" in args
        yield args


def test_readme_workflow_through_real_sdk_preserves_labels_and_parents(transport, monkeypatch):
    states, calls, _ = transport
    before = deepcopy(states)
    monkeypatch.setenv("META_CLI_ENVIRONMENT", "second")
    commands = list(documented_commands())
    assert len(commands) == 13  # Fail when examples change until reviewed here.
    for args in commands:
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        if args[1] == "get":
            assert data["account_id"] == "456"
        else:
            assert data["environment"] == "second" and data["account_id"] == "act_456"
        assert "synthetic-" not in result.output
    assert {call[0] for call in calls} == {"second"}
    assert writes(calls) == [
        ("second", "POST", "act_456", "adlabels", {"name": "Winner"}),
        ("second", "POST", "100", "adlabels", {"adlabels": [{"id": "901"}]}),
        ("second", "POST", "300", "adlabels", {"adlabels": [{"id": "901"}]}),
        ("second", "POST", "100", "", {"status": "ARCHIVED"}),
    ]
    assert states["first"] == before["first"]
    assert states["second"]["300"] == {**before["second"]["300"], "adlabels": [OTHER, WINNER]}
    assert states["second"]["100"] == {
        **before["second"]["100"], "adlabels": [OTHER, WINNER],
        "status": "ARCHIVED", "configured_status": "ARCHIVED", "effective_status": "ARCHIVED",
    }
    # Repeating all mutations is a no-op without confirmation or further POSTs.
    for args, outcome in zip(MUTATIONS, ["already_exists", "already_applied",
                                        "already_applied", "already_archived"], strict=True):
        data = invoke(args)
        assert data["outcome"] == outcome and data["changed"] is False
    assert len(writes(calls)) == 4


@pytest.mark.parametrize("override", [None, "second"])
@pytest.mark.parametrize("args", COMMANDS)
def test_routing_of_every_read_and_preview_without_writes(transport, monkeypatch, override, args):
    states, calls, _ = transport
    if override:
        monkeypatch.setenv("META_CLI_ENVIRONMENT", override)
    selected = override or "first"
    states[selected]["labels"].append(WINNER)
    before = deepcopy(states)
    flags = ["--dry-run"] if args in MUTATIONS else []
    data = invoke([*args, *flags])
    assert calls and {call[0] for call in calls} == {selected}
    assert not writes(calls) and states == before
    if args[1] != "get":
        assert data["environment"] == selected
    if args[1] == "get":
        assert {"account_id", "id", "name", "adlabels", "status", "configured_status",
                "effective_status"} <= data.keys()
        if args[0] == "ads":
            assert data["adset_id"] == "200" and data["campaign_id"] == "300"
        else:
            assert data["daily_budget"] == "1000" and data["lifetime_budget"] == "0"


def test_process_override_does_not_leak_between_cli_invocations(transport, monkeypatch):
    _, calls, _ = transport
    for selection in ("second", "first", None):
        if selection:
            monkeypatch.setenv("META_CLI_ENVIRONMENT", selection)
        else:
            monkeypatch.delenv("META_CLI_ENVIRONMENT")
        data = invoke(["labels", "create", "--name", "Winner", "--yes"])
        assert data["environment"] == (selection or "first")
    assert [(c[0], c[2]) for c in writes(calls)] == [("second", "act_456"), ("first", "act_123")]


@pytest.mark.parametrize("override", ["missing", " second ", ""])
@pytest.mark.parametrize("args", COMMANDS)
def test_invalid_override_fails_before_sdk_even_for_dry_runs(transport, monkeypatch, override, args):
    _, calls, _ = transport
    monkeypatch.setenv("META_CLI_ENVIRONMENT", override)
    flags = ["--dry-run", "--yes"] if args in MUTATIONS else []
    result = runner.invoke(app, [*args, *flags, "--json"])
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["ok"] is False
    assert calls == []


@pytest.mark.parametrize("args", MUTATIONS)
@pytest.mark.parametrize("answer", ["n\n", ""])
def test_confirmation_decline_and_eof_never_write(transport, args, answer):
    states, calls, _ = transport
    if args[1] == "add-label":
        states["first"]["labels"].append(WINNER)
    result = runner.invoke(app, [*args, "--json"], input=answer)
    assert result.exit_code == 1
    assert "first / act_123" in result.output
    assert not writes(calls)


@pytest.mark.parametrize("stage", ["GET", "POST"])
@pytest.mark.parametrize("args", MUTATIONS)
def test_transport_failures_redacted_with_no_retry(transport, monkeypatch, stage, args):
    states, calls, failures = transport
    monkeypatch.setenv("META_CLI_ENVIRONMENT", "second")
    if args[1] == "add-label":
        states["second"]["labels"].append(WINNER)
    failures[stage] = True
    result = runner.invoke(app, [*args, "--yes", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["ok"] is False and "[REDACTED]" in data["error"]
    assert "synthetic-second-" not in result.output
    assert len(writes(calls)) == (1 if stage == "POST" else 0)


@pytest.mark.parametrize("args", COMMANDS)
def test_registered_help_requires_no_credentials_or_sdk(transport, monkeypatch, args):
    _, calls, _ = transport
    monkeypatch.setenv("META_CLI_ENVIRONMENT", "missing")
    result = runner.invoke(app, [*args[:2], "--help"])
    assert result.exit_code == 0, result.output
    assert "--json" in result.output
    if args in MUTATIONS:
        for flag in ("--dry-run", "--yes"):
            assert flag in result.output
    assert not calls


@pytest.mark.parametrize("args", [
    ["labels", "create"], ["ads", "archive"], ["ads", "archive", "100", "200"],
    ["ads", "add-label", "100"], ["campaigns", "add-label", "--label-id", "901"],
    ["labels", "list", "--environment", "second"],
])
def test_argument_errors_exit_two_without_sdk(transport, args):
    _, calls, _ = transport
    result = runner.invoke(app, args)
    assert result.exit_code == 2, result.output
    assert not calls

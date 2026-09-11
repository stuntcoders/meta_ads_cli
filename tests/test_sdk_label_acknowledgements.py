"""Real generated SDK requests/parsers with synthetic transport responses only."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from facebook_business.adobjects.objectparser import ObjectParser
from facebook_business.api import FacebookAdsApi, FacebookResponse
from test_labels_archive_workflow import OTHER, WINNER, runner, writes
from test_labels_archive_workflow import transport as transport

from meta_cli.app import app


@pytest.fixture(params=[("ads", "100"), ("campaigns", "300")])
def label_case(transport, request):
    states, calls, _ = transport
    kind, node = request.param
    states["first"]["labels"].append(deepcopy(WINNER))
    return SimpleNamespace(
        states=states, calls=calls, node=node, before=deepcopy(states),
        args=[kind, "add-label", node, "--label-id", "901", "--yes", "--json"],
    )


@pytest.fixture
def intercept(monkeypatch):
    original = FacebookAdsApi.call

    def install(transform):
        def call(api, method, path, **kwargs):
            response = original(api, method, path, **kwargs)
            body = transform(method, *path, response.json())
            return FacebookResponse(body=json.dumps(body), http_status=200, headers={})
        monkeypatch.setattr(FacebookAdsApi, "call", call)
    return install


def invoke(case):
    result = runner.invoke(app, case.args)
    return result, json.loads(result.output)


def assert_one_addition(case):
    assert writes(case.calls) == [
        ("first", "POST", case.node, "adlabels", {"adlabels": [{"id": "901"}]}),
    ]
    expected = deepcopy(case.before)
    expected["first"][case.node]["adlabels"].append(WINNER)
    assert case.states == expected  # Includes other account, parents, budgets, creative and statuses.


@pytest.mark.parametrize("ack", [{"success": True}, {}, {"id": "TARGET"},
                                  {"data": {"success": True}}])
def test_acknowledgement_requires_verified_readback(label_case, intercept, monkeypatch, ack):
    case = label_case
    ack = {**ack, "id": case.node} if "id" in ack else ack
    parsed = []
    original = ObjectParser.parse_single

    def parse(parser, response, *args, **kwargs):
        before = deepcopy(response)
        result = original(parser, response, *args, **kwargs)
        parsed.append((before, result.export_all_data()))
        return result

    monkeypatch.setattr(ObjectParser, "parse_single", parse)
    intercept(lambda method, node, edge, body: deepcopy(ack) if method == "POST" else body)
    result, data = invoke(case)
    assert result.exit_code == 0, result.output
    assert data["verified"] is True and data["outcome"] == "added" and data["changed"] is True
    assert data["object_id"] == case.node and data["account_id"] == "act_123"
    assert data["before_label_ids"] == ["902"] and data["after_label_ids"] == ["902", "901"]
    if ack == {"success": True}:
        assert ({"success": True}, {}) in parsed  # Actual SDK stripping, not an invented ID.
    assert case.calls[-1][1:4] == ("GET", case.node, "")
    assert_one_addition(case)


@pytest.mark.parametrize("ack", [
    None, False, [], "invalid", {"unexpected": True}, {"success": False},
    {"success": False, "id": "TARGET"}, {"success": 0}, {"success": 1},
    {"success": "true"}, {"success": None}, {"id": "999"},
    {"success": True, "id": "999"}, {"success": True, "id": None},
    {"success": False, "data": {"id": "TARGET"}},
    {"data": {"success": False, "id": "TARGET"}},
    {"error": {"message": "Synthetic permission error", "code": 200}},
])
def test_negative_or_malformed_write_stays_error_even_if_state_matches(label_case, intercept, ack):
    case = label_case
    ack = json.loads(json.dumps(ack).replace("TARGET", case.node))
    intercept(lambda method, node, edge, body: deepcopy(ack) if method == "POST" else body)
    result, data = invoke(case)
    assert result.exit_code == 1, result.output
    assert data["ok"] is False and "before retrying" in data["error"]
    assert case.calls[-1][1] == "POST"  # Never turn a negative acknowledgement into success.
    assert_one_addition(case)  # Even with matching state, no retries or rollback.


@pytest.mark.parametrize("ack", [{"success": True}, {}])
@pytest.mark.parametrize("problem", [
    "missing_requested", "missing_prior", "missing_id", "wrong_id", "missing_account",
    "wrong_account", "missing_labels_invalid_edge", "null_labels", "partial_labels", "invalid_label",
    "duplicate_labels", "empty", "false", "error", "transport_error",
])
def test_inconclusive_readback_never_reports_success(label_case, intercept, ack, problem):
    case = label_case

    def transform(method, node, edge, body):
        if method == "POST":
            return deepcopy(ack)
        if node != case.node or not writes(case.calls):
            return body
        if problem == "missing_labels_invalid_edge":
            if edge == "adlabels":
                return {}  # Absence alone is safe only if the fallback edge succeeds.
            del body["adlabels"]
        elif problem == "missing_requested":
            body["adlabels"] = [OTHER]
        elif problem == "missing_prior":
            body["adlabels"] = [WINNER]
        elif problem.startswith("missing_"):
            del body[{"missing_id": "id", "missing_account": "account_id"}[problem]]
        elif problem == "wrong_id":
            body["id"] = "999"
        elif problem == "wrong_account":
            body["account_id"] = "999"
        elif problem == "null_labels":
            body["adlabels"] = None
        elif problem == "partial_labels":
            body["adlabels"] = {"data": [OTHER, WINNER], "paging": {"next": "more"}}
        elif problem == "invalid_label":
            body["adlabels"] = [OTHER, WINNER, {}]
        elif problem == "duplicate_labels":
            body["adlabels"] = [OTHER, WINNER, WINNER]
        elif problem == "empty":
            return {}
        elif problem == "false":
            body["success"] = False
        elif problem == "error":
            return {"error": {"message": "Synthetic readback failure", "code": 200}}
        elif problem == "transport_error":
            raise RuntimeError("Readback synthetic-first-token synthetic-first-secret")
        return body

    intercept(transform)
    result, data = invoke(case)
    assert result.exit_code == 1, result.output
    assert data["ok"] is False
    assert "may have succeeded, but verification failed" in data["error"]
    assert "synthetic-first-" not in result.output
    expected_edge = "adlabels" if problem == "missing_labels_invalid_edge" else ""
    assert case.calls[-1][1:4] == ("GET", case.node, expected_edge)
    assert_one_addition(case)


def test_preflight_requires_server_returned_identity(label_case, intercept):
    case = label_case

    def transform(method, node, edge, body):
        if node == case.node:
            body.pop("id")
        return body

    intercept(transform)
    result, data = invoke(case)
    assert result.exit_code == 1 and data["ok"] is False
    assert not writes(case.calls) and case.states == case.before


@pytest.mark.parametrize("operation", ["create", "archive"])
@pytest.mark.parametrize("ack", [
    {"success": False}, {"success": False, "id": "TARGET"},
    {"success": 1, "id": "TARGET"}, {},
])
def test_related_mutations_reject_flags_before_sdk_strips_them(transport, intercept, operation, ack):
    _, calls, _ = transport
    node = "901" if operation == "create" else "100"
    ack = json.loads(json.dumps(ack).replace("TARGET", node))
    intercept(lambda method, node, edge, body: deepcopy(ack) if method == "POST" else body)
    args = (["labels", "create", "--name", "Winner"] if operation == "create"
            else ["ads", "archive", "100"])
    result = runner.invoke(app, [*args, "--yes", "--json"])
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["ok"] is False
    assert calls[-1][1] == "POST" and len(writes(calls)) == 1


def test_archive_success_only_acknowledgement_still_reads_back(transport, intercept):
    _, calls, _ = transport
    intercept(lambda method, node, edge, body: {"success": True} if method == "POST" else body)
    result = runner.invoke(app, ["ads", "archive", "100", "--yes", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["verified"] is True
    assert calls[-1][1:4] == ("GET", "100", "") and len(writes(calls)) == 1

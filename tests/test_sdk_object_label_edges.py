"""Missing node fields resolved by real SDK Cursor/parsers, with transport mocked.

Both CLI paths use temporary synthetic profiles. All socket and requests traffic
is forbidden; no label creation or actual account operation occurs.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from facebook_business.api import FacebookAdsApi, FacebookResponse
from facebook_business.exceptions import FacebookRequestError
from test_labels_archive_workflow import OTHER, writes
from test_labels_archive_workflow import transport as transport
from test_sdk_label_acknowledgements import assert_one_addition, invoke
from test_sdk_label_acknowledgements import label_case as label_case

TOKEN = "synthetic-first-token"
SECRET = "synthetic-first-secret"


def page(ids, after=None):
    body = {"data": [{"id": value} for value in ids]}
    if after is not None:
        body["paging"] = {"next": "https://example.invalid/next", "cursors": {"after": after}}
    return body


@pytest.fixture
def edge_case(label_case, monkeypatch):
    case = label_case
    original = FacebookAdsApi.call
    network = Mock(side_effect=AssertionError("Socket access forbidden"))
    monkeypatch.setattr("socket.socket.connect", network)
    control = SimpleNamespace(
        case=case, initial=None, readback=None, omit_initial=True, omit_readback=True,
        index=0, consumed=[],
    )

    def call(api, method, path, params=None, **kwargs):
        is_target = path[0] == case.node
        phase = "readback" if writes(case.calls) else "initial"
        if is_target and method == "POST" and control.initial is not None:
            assert control.index == len(control.initial), "Write before complete pagination"
        response = original(api, method, path, params=params, **kwargs)
        if method != "GET" or not is_target:
            return response
        body = response.json()
        if not path[1]:
            control.index = 0
            if getattr(control, f"omit_{phase}"):
                del body["adlabels"]
        elif path[1] == "adlabels":
            pages = getattr(control, phase)
            if pages is not None:
                index = control.index
                assert index < len(pages), "Unexpected extra page request"
                expected = {"fields": "id,name"}
                if index:
                    expected["after"] = pages[index - 1]["paging"]["cursors"]["after"]
                assert params == expected
                body = pages[index] if isinstance(pages[index], Exception) else deepcopy(pages[index])
            else:
                assert params == {"fields": "id,name"}
            control.index += 1
            control.consumed.append((phase, deepcopy(params)))
            if isinstance(body, Exception):
                raise body
        else:
            pytest.fail("Unexpected target edge")
        # Returning raw Python envelopes exercises Cursor and its scoped parser,
        # including envelopes that FacebookResponse.json() may return as null.
        return FacebookResponse(body=body, http_status=200, headers={})

    monkeypatch.setattr(FacebookAdsApi, "call", call)
    yield control
    network.assert_not_called()


def configure(control, ids, pages):
    rows = [{"id": value} for value in ids]
    control.case.states["first"][control.case.node]["adlabels"] = rows
    control.case.before = deepcopy(control.case.states)
    control.initial = deepcopy(pages)


def edge_calls(case):
    return [c for c in case.calls if c[1:4] == ("GET", case.node, "adlabels")]


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("ids,pages", [
    ([], [page([])]),
    ([], [{"data": [], "paging": {"cursors": {"before": "first", "after": "last"}}}]),
    ([], [page([], "a"), page([])]),
    (["902", "903", "904"], [page(["902"], "a"), page(["903"], "b"), page(["904"])]),
    (["902", "903"], [page(["902"], "a"), page([], "b"), page(["903"])]),
    (["902"], [page([], "a"), page(["902"])]),
])
def test_complete_edges_preserve_every_label_and_repeat_without_writes(edge_case, ids, pages, preview):
    control, case = edge_case, edge_case.case
    configure(control, ids, pages)
    if preview:
        case.args.append("--dry-run")
    else:
        # Readback must itself consume multiple pages, including an empty one.
        control.readback = [page(ids, "r1"), page([], "r2"), page(["901"])]
    result, data = invoke(case)
    assert result.exit_code == 0, result.output
    assert data["before_label_ids"] == ids
    assert data["mutation"] == {"adlabels": [{"id": "901"}]}
    assert data["outcome"] == ("would_add" if preview else "added")
    assert data["changed"] is (not preview)
    assert len([p for phase, p in control.consumed if phase == "initial"]) == len(pages)
    if preview:
        assert not writes(case.calls) and case.states == case.before
        assert "verified" not in data
        assert len(edge_calls(case)) == len(pages)
    else:
        assert data["verified"] is True
        assert data["after_label_ids"] == ids + ["901"]
        assert len(edge_calls(case)) == len(pages) + 3
        assert_one_addition(case)
        # Repeated add resolves the missing field again but does not prompt/POST.
        case.args.remove("--yes")
        result, repeated = invoke(case)
        assert result.exit_code == 0, result.output
        assert repeated["outcome"] == "already_applied" and repeated["changed"] is False
        assert repeated["before_label_ids"] == ids + ["901"]
        assert len(edge_calls(case)) == len(pages) + 6
        assert_one_addition(case)


@pytest.mark.parametrize("flags", [[], ["--yes"], ["--dry-run"]])
def test_already_present_on_final_page_is_noop(edge_case, flags):
    control, case = edge_case, edge_case.case
    configure(control, ["902", "901"], [page(["902"], "a"), page([], "b"), page(["901"])])
    case.args = [arg for arg in case.args if arg != "--yes"] + flags
    result, data = invoke(case)
    assert result.exit_code == 0, result.output
    assert data["outcome"] == "already_applied" and data["changed"] is False
    assert data["before_label_ids"] == ["902", "901"]
    assert len(edge_calls(case)) == 3
    assert not writes(case.calls) and case.states == case.before


def test_unsafe_edge_fails_even_in_dry_run(edge_case):
    case = edge_case.case
    edge_case.initial = [page(["902"], "a"), {}]
    case.args.append("--dry-run")
    result, data = invoke(case)
    assert result.exit_code == 1 and data["ok"] is False
    assert len(edge_calls(case)) == 2
    assert not writes(case.calls) and case.states == case.before


def test_general_get_keeps_omitted_field_raw(edge_case):
    case = edge_case.case
    case.args = [case.args[0], "get", case.node, "--json"]
    result, data = invoke(case)
    assert result.exit_code == 0, result.output
    assert data["id"] == case.node and "adlabels" not in data
    assert not edge_calls(case) and not writes(case.calls)


def test_only_readback_missing_field_resolves_edge(edge_case):
    edge_case.omit_initial = False
    result, data = invoke(edge_case.case)
    assert result.exit_code == 0, result.output
    assert data["verified"] is True
    assert data["after_label_ids"] == ["902", "901"]
    assert edge_case.consumed == [("readback", {"fields": "id,name"})]
    assert_one_addition(edge_case.case)


BAD_PAGES = [
    pytest.param(None, id="null-envelope"),
    pytest.param([], id="list-envelope"),
    pytest.param({}, id="missing-data"),
    pytest.param({"data": None}, id="null-data"),
    pytest.param({"data": {}}, id="object-data"),
    pytest.param({"data": [None]}, id="null-row"),
    pytest.param({"data": [{}]}, id="missing-id"),
    pytest.param(page(["bad"]), id="invalid-id"),
    pytest.param(page(["９０１"]), id="non-ascii-id"),
    pytest.param(page([True]), id="boolean-id"),
    pytest.param({"data": [], "error": {"message": TOKEN + SECRET}}, id="graph-error"),
    pytest.param({"data": [], "success": False}, id="negative-success"),
    pytest.param({"data": [], "success": 1}, id="non-boolean-success"),
    pytest.param({"data": [{"id": "901", "error": {}}]}, id="row-error"),
    pytest.param({"data": [{"id": "901", "success": False}]}, id="row-negative-success"),
    pytest.param({"data": [], "paging": None}, id="null-paging"),
    pytest.param({"data": [], "paging": []}, id="list-paging"),
    pytest.param({"data": [], "paging": {"next": "more"}}, id="next-without-cursor"),
    pytest.param({"data": [], "paging": {"cursors": None}}, id="null-cursors"),
    pytest.param({"data": [], "paging": {"cursors": {"after": ""}}}, id="empty-cursor"),
    pytest.param({"data": [], "paging": {"cursors": {"before": 1}}}, id="invalid-before"),
    pytest.param({"data": [], "paging": {"next": None, "cursors": {"after": "b"}}}, id="null-next"),
    pytest.param(page(["904", "904"]), id="duplicate-ids"),
    pytest.param(RuntimeError(f"Synthetic edge failure {TOKEN} {SECRET}"), id="transport-error"),
    pytest.param(FacebookRequestError(
        "Synthetic denied edge", {"method": "GET", "params": {"access_token": TOKEN}},
        403, {}, {"error": {"code": 200, "message": f"Denied {SECRET}"}},
    ), id="sdk-request-error"),
]


@pytest.mark.parametrize("bad", BAD_PAGES)
@pytest.mark.parametrize("later_page", [False, True])
@pytest.mark.parametrize("phase", ["initial", "readback"])
def test_unsafe_edges_never_claim_success(edge_case, bad, later_page, phase, capsys, caplog):
    control, case = edge_case, edge_case.case
    pages = [page(["902"], "a")] if later_page else []
    pages.append(bad)
    setattr(control, phase, pages)
    result, data = invoke(case)
    assert result.exit_code == 1, result.output
    assert data["ok"] is False and "verified" not in data
    assert "Failed to resolve complete labels" in data["error"]
    consumed = [p for p_phase, p in control.consumed if p_phase == phase]
    assert len(consumed) == len(pages)
    assert consumed[0] == {"fields": "id,name"}
    if later_page:
        assert consumed[1] == {"fields": "id,name", "after": "a"}
    assert case.calls[-1][1:4] == ("GET", case.node, "adlabels")
    if phase == "initial":
        assert not writes(case.calls) and case.states == case.before
        # Initial label resolution precedes account-label enumeration as well.
        assert not any(c[2:4] == ("act_123", "adlabels") for c in case.calls)
    else:
        assert "may have succeeded, but verification failed" in data["error"]
        assert "no rollback" in data["error"]
        assert_one_addition(case)
    captured = capsys.readouterr()
    for text in (result.output, str(result.exception), captured.out, captured.err, caplog.text):
        assert TOKEN not in text and SECRET not in text
    if isinstance(bad, Exception):
        assert "[REDACTED]" in data["error"]


@pytest.mark.parametrize("last", [page(["902"]), page([], "a")], ids=["cross-page-duplicate", "cursor-cycle"])
@pytest.mark.parametrize("phase", ["initial", "readback"])
def test_duplicates_and_nonprogress_fail_closed(edge_case, last, phase):
    setattr(edge_case, phase, [page(["902"], "a"), last])
    result, data = invoke(edge_case.case)
    assert result.exit_code == 1, result.output
    assert data["ok"] is False and "verified" not in data
    assert len([p for p_phase, p in edge_case.consumed if p_phase == phase]) == 2
    assert len(writes(edge_case.case.calls)) == int(phase == "readback")


@pytest.mark.parametrize("ids", [[], ["901"], ["902"]])
def test_complete_readback_still_requires_prior_and_requested_labels(edge_case, ids):
    edge_case.readback = [page(ids)]
    result, data = invoke(edge_case.case)
    assert result.exit_code == 1, result.output
    assert "Readback did not retain all prior labels and the requested label" in data["error"]
    assert "verified" not in data
    assert_one_addition(edge_case.case)


def test_complete_readback_accepts_concurrent_extra_label(edge_case):
    edge_case.readback = [page(["902"], "a"), page(["901", "903"])]
    result, data = invoke(edge_case.case)
    assert result.exit_code == 0, result.output
    assert data["verified"] is True and data["after_label_ids"] == ["902", "901", "903"]
    assert_one_addition(edge_case.case)


@pytest.mark.parametrize("field,value", [("id", "999"), ("account_id", "999")])
def test_missing_field_does_not_bypass_identity_or_ownership(edge_case, field, value):
    case = edge_case.case
    case.states["first"][case.node][field] = value
    result, data = invoke(case)
    assert result.exit_code == 1 and data["ok"] is False
    assert not edge_calls(case) and not writes(case.calls)


def test_explicit_lists_do_not_query_edge(edge_case):
    edge_case.omit_initial = edge_case.omit_readback = False
    result, data = invoke(edge_case.case)
    assert result.exit_code == 0, result.output
    assert data["verified"] is True
    assert not edge_calls(edge_case.case)
    assert_one_addition(edge_case.case)


@pytest.mark.parametrize("value", [None, {}, {"data": []}, [None], [{}], [OTHER, OTHER]])
def test_explicit_unsafe_fields_never_fall_back(edge_case, value):
    case = edge_case.case
    edge_case.omit_initial = False
    case.states["first"][case.node]["adlabels"] = value
    result, data = invoke(case)
    assert result.exit_code == 1 and data["ok"] is False
    assert not edge_calls(case) and not writes(case.calls)

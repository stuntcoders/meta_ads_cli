"""Live API shape regression with synthetic SDK transport only."""
import json
from copy import deepcopy

import pytest
from facebook_business.api import FacebookAdsApi, FacebookResponse
from facebook_business.exceptions import FacebookRequestError
from test_labels_archive_workflow import transport as transport
from test_sdk_label_acknowledgements import assert_one_addition, invoke
from test_sdk_label_acknowledgements import label_case as label_case


@pytest.mark.parametrize('preview', [False, True])
@pytest.mark.parametrize('empty', [False, True])
def test_unsupported_forward_edge_uses_complete_reverse_membership(label_case, monkeypatch, preview, empty):
    case = label_case
    if empty:
        case.states['first'][case.node]['adlabels'] = []
        case.before = deepcopy(case.states)
    original = FacebookAdsApi.call
    reverse_reads = []

    def call(api, method, path, params=None, **kwargs):
        node, edge = path
        if method == 'GET' and node == case.node and edge == 'adlabels':
            raise FacebookRequestError('Synthetic unsupported edge', {}, 400, {}, {
                'error': {'code': 100, 'message': 'Tried accessing nonexisting field (adlabels)'},
            })
        if method == 'GET' and node in {'901', '902'} and edge in {'ads', 'campaigns'}:
            reverse_reads.append((node, edge))
            members = case.states['first'][case.node]['adlabels']
            present = any(str(x['id']) == node for x in members)
            return FacebookResponse(body=json.dumps({'data': [{'id': case.node}] if present else []}),
                                    http_status=200, headers={})
        response = original(api, method, path, params=params, **kwargs)
        if method == 'GET' and node == case.node and not edge:
            body = response.json()
            body.pop('adlabels', None)
            return FacebookResponse(body=json.dumps(body), http_status=200, headers={})
        return response

    monkeypatch.setattr(FacebookAdsApi, 'call', call)
    if preview:
        case.args.append('--dry-run')
    result, data = invoke(case)
    assert result.exit_code == 0, result.output
    assert reverse_reads
    assert data['before_label_ids'] == ([] if empty else ['902'])
    if preview:
        assert case.states == case.before
    else:
        assert data['verified']
        assert_one_addition(case)

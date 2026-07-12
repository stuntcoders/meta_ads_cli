from __future__ import annotations

from meta_cli.config import MetaCredentials
from meta_cli.sdk import MetaSDKClient


def _creds() -> MetaCredentials:
    return MetaCredentials.model_validate(
        {
            "META_ACCESS_TOKEN": "token",
            "META_APP_ID": "app",
            "META_APP_SECRET": "secret",
            "META_AD_ACCOUNT_ID": "act_123",
        }
    )


class PreloadedCursor:
    def __init__(self, first_page, next_pages=None):
        self._queue = list(first_page)
        self._next_pages = list(next_pages or [])
        self._total = len(self._queue) + sum(len(page) for page in self._next_pages)
        self._finished_iteration = not bool(self._next_pages)
        self.load_next_page_calls = 0
        self.params = {"limit": 50, "fields": "id,name", "summary": True}

    def __len__(self):
        return len(self._queue)

    def __getitem__(self, index):
        return self._queue[index]

    def total(self):
        return self._total

    def load_next_page(self):
        self.load_next_page_calls += 1
        if not self._next_pages:
            self._finished_iteration = True
            return False
        self._queue = list(self._next_pages.pop(0))
        self._finished_iteration = not bool(self._next_pages)
        return True


def test_collect_cursor_consumes_preloaded_first_page():
    client = MetaSDKClient(_creds())
    cursor = PreloadedCursor(first_page=[{"id": "c1"}, {"id": "c2"}], next_pages=[])

    rows, paging = client._collect_cursor(cursor, auto_paginate=True)

    assert [item["id"] for item in rows] == ["c1", "c2"]
    assert paging["pages_fetched"] == 1
    assert paging["total_count"] == 2
    assert paging["has_more"] is False
    assert cursor.load_next_page_calls == 1


def test_collect_cursor_consumes_all_pages_once_in_order():
    client = MetaSDKClient(_creds())
    cursor = PreloadedCursor(
        first_page=[{"id": "c1"}, {"id": "c2"}],
        next_pages=[[{"id": "c3"}], [{"id": "c4"}, {"id": "c5"}]],
    )

    rows, paging = client._collect_cursor(cursor, auto_paginate=True)

    assert [item["id"] for item in rows] == ["c1", "c2", "c3", "c4", "c5"]
    assert paging["pages_fetched"] == 3
    assert paging["total_count"] == 5
    assert paging["has_more"] is False
    assert cursor.load_next_page_calls == 3


def test_list_and_insights_results_include_preloaded_cursor_data(monkeypatch):
    client = MetaSDKClient(_creds())

    class Account:
        def get_campaigns(self, fields, params):
            return PreloadedCursor([{"id": "campaign-1"}])

        def get_insights(self, fields, params):
            return PreloadedCursor([{"ad_id": "ad-1", "spend": "12.34"}])

    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_ad_account", lambda: Account())

    campaigns = client.list_campaigns(fields=["id"], include_paging=True)
    insights = client.get_ad_insights(fields=["ad_id", "spend"], include_paging=True)

    assert campaigns["data"] == [{"id": "campaign-1"}]
    assert campaigns["paging"]["total_count"] == 1
    assert insights["data"] == [{"ad_id": "ad-1", "spend": "12.34"}]
    assert insights["paging"]["total_count"] == 1


def test_collect_cursor_no_paginate_stops_after_first_page():
    client = MetaSDKClient(_creds())
    cursor = PreloadedCursor(
        first_page=[{"id": "c1"}],
        next_pages=[[{"id": "c2"}], [{"id": "c3"}]],
    )

    rows, paging = client._collect_cursor(cursor, auto_paginate=False)

    assert [item["id"] for item in rows] == ["c1"]
    assert paging["pages_fetched"] == 1
    assert paging["has_more"] is True

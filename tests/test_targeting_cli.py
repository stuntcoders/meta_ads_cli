from __future__ import annotations

import json

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeClient:
    def __init__(self):
        self.last_search = None
        self.last_interest_search = None
        self.last_category_search = None

    def search_targeting_interests(self, query):
        self.last_interest_search = {"query": query}
        return [
            {
                "id": "interest_1",
                "name": "Tutoring",
                "audience_size_lower_bound": 1000,
                "audience_size_upper_bound": 2000,
                "path": ["Interests", "Education"],
            }
        ]

    def search_targeting_categories(self, demographic_class):
        self.last_category_search = {"demographic_class": demographic_class}
        return [
            {
                "id": "family_1",
                "name": "Parents with teenagers",
                "type": "family_statuses",
                "description": "Parents of children aged 13 to 17",
                "path": ["Demographics", "Parents"],
            },
            {
                "id": "family_2",
                "name": "New parents",
                "type": "family_statuses",
                "description": "Parents with a child under 12 months",
                "path": ["Demographics", "Parents"],
            },
        ]

    def search_targeting_locations(self, query, countries=None):
        self.last_search = {"query": query, "countries": countries}
        return [
            {
                "key": "city_1",
                "name": "Gurugram",
                "type": "city",
                "country_code": "IN",
                "region": "Haryana",
            }
        ]


def test_search_interests_json(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("meta_cli.commands.targeting.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        ["targeting", "search-interests", "--query", "Tutoring", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"][0]["id"] == "interest_1"
    assert fake.last_interest_search == {"query": "Tutoring"}


def test_search_interests_table(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.targeting.build_client", lambda *_: FakeClient())

    result = runner.invoke(
        app,
        ["targeting", "search-interests", "--query", "Tutoring"],
    )

    assert result.exit_code == 0
    assert "Tutoring" in result.stdout
    assert "Education" in result.stdout


def test_search_categories_json_and_query_filter(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("meta_cli.commands.targeting.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        [
            "targeting",
            "search-categories",
            "--class",
            "family_statuses",
            "--query",
            "teen",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["class"] == "family_statuses"
    assert payload["query"] == "teen"
    assert [item["id"] for item in payload["data"]] == ["family_1"]
    assert fake.last_category_search == {"demographic_class": "family_statuses"}


def test_search_categories_rejects_unsupported_class(monkeypatch):
    def fail_build_client(*_args):
        raise AssertionError("invalid class must fail before building client")

    monkeypatch.setattr("meta_cli.commands.targeting.build_client", fail_build_client)
    result = runner.invoke(
        app,
        ["targeting", "search-categories", "--class", "unknown", "--json"],
    )

    assert result.exit_code == 1
    assert "Unsupported targeting category class" in json.loads(result.stdout)["error"]


def test_search_locations_json(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("meta_cli.commands.targeting.build_client", lambda *_: fake)

    result = runner.invoke(
        app,
        ["targeting", "search-locations", "--query", "Gurugram", "--country", "in", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"][0]["key"] == "city_1"
    assert fake.last_search == {"query": "Gurugram", "countries": ["IN"]}


def test_search_locations_table(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.targeting.build_client", lambda *_: FakeClient())

    result = runner.invoke(
        app,
        ["targeting", "search-locations", "--query", "Gurugram"],
    )

    assert result.exit_code == 0
    assert "Gurugram" in result.stdout
    assert "Haryana" in result.stdout

from __future__ import annotations

import json

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeClient:
    def __init__(self):
        self.last_search = None
        self.last_interest_search = None

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

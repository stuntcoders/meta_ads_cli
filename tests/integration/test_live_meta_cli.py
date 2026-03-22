from __future__ import annotations

import os

import pytest
from typer.testing import CliRunner

from meta_cli.app import app

pytestmark = pytest.mark.skipif(
    os.getenv("LIVE_META_TESTS") != "1",
    reason="Set LIVE_META_TESTS=1 to run live Meta integration tests",
)

runner = CliRunner()


@pytest.mark.integration
def test_live_auth_test_command() -> None:
    required = [
        "META_ACCESS_TOKEN",
        "META_APP_ID",
        "META_APP_SECRET",
        "META_AD_ACCOUNT_ID",
    ]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        pytest.skip(f"Missing required env vars for live test: {', '.join(missing)}")

    result = runner.invoke(app, ["auth", "test", "--json"])
    assert result.exit_code == 0, result.stdout
    assert '"ok": true' in result.stdout.lower()

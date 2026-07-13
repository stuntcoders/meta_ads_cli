from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PI_ARTIFACT_PATTERN = "/tmp/pi-long-task/"


def test_pi_long_task_artifacts_are_ignored_and_excluded_from_packages() -> None:
    ignore_rules = {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_excludes = pyproject["tool"]["hatch"]["build"]["exclude"]

    assert PI_ARTIFACT_PATTERN in ignore_rules
    assert PI_ARTIFACT_PATTERN in package_excludes

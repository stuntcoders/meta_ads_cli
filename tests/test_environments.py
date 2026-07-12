from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from meta_cli.environments import (
    EnvironmentsFile,
    EnvironmentStore,
    environments_file_path,
)
from meta_cli.exceptions import ConfigError

ENVIRONMENTS_YAML = """
profiles:
  agency:
    display_name: Agency account
    access_token: agency-token
    app_id: "101"
    app_secret: agency-secret
    ad_account_id: "12345"
    api_version: v23.0
    system_user_id: "201"
    facebook_page_id: "301"
    instagram_user_id: "401"
  sandbox:
    access_token: sandbox-token
    app_id: "102"
    app_secret: sandbox-secret
    ad_account_id: act_67890
""".strip()


def test_environment_config_loads_multiple_profiles_from_override(tmp_path, monkeypatch):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(path))

    config = EnvironmentStore().load()

    assert set(config.profiles) == {"agency", "sandbox"}
    agency = config.profiles["agency"]
    assert agency.access_token.get_secret_value() == "agency-token"
    assert agency.app_id == "101"
    assert agency.app_secret.get_secret_value() == "agency-secret"
    assert agency.ad_account_id == "act_12345"
    assert agency.api_version == "v23.0"
    assert agency.display_name == "Agency account"
    assert agency.system_user_id == "201"
    assert agency.facebook_page_id == "301"
    assert agency.instagram_user_id == "401"
    assert config.profiles["sandbox"].api_version == "v25.0"
    assert config.active_profile is None


def test_environment_store_selection_persists_across_instances_and_processes(
    tmp_path, monkeypatch
):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(path))

    EnvironmentStore().select_profile("sandbox")

    assert EnvironmentStore().active_profile_name() == "sandbox"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from meta_cli.environments import EnvironmentStore; "
                "print(EnvironmentStore().active_profile_name())"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "META_CLI_ENVIRONMENTS_FILE": str(path),
            "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
        },
    )
    assert result.stdout.strip() == "sandbox"


def test_environment_store_absent_file_has_no_automatic_selection(tmp_path, monkeypatch):
    path = tmp_path / "missing" / "environments.yaml"
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(path))

    store = EnvironmentStore()

    assert store.active_profile_name() is None
    assert store.get_active_profile() is None
    assert not path.exists()


def test_environment_store_unknown_profile_lookup_and_selection_fail(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)
    store = EnvironmentStore(path)

    with pytest.raises(ConfigError, match="profile not found: missing"):
        store.get_profile("missing")
    with pytest.raises(ConfigError, match="profile not found: missing"):
        store.select_profile("missing")

    assert store.active_profile_name() is None


def test_environment_store_selection_can_be_cleared(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)
    store = EnvironmentStore(path)
    store.select_profile("agency")

    store.select_profile(None)

    assert EnvironmentStore(path).active_profile_name() is None


@pytest.mark.parametrize(
    "contents, error",
    [
        ("profiles: [unterminated", "Unable to read environments file"),
        ("- not\n- a\n- mapping", "Invalid environments file structure"),
    ],
)
def test_environment_store_rejects_malformed_yaml_and_non_mapping(
    tmp_path, contents, error
):
    path = tmp_path / "environments.yaml"
    path.write_text(contents)

    with pytest.raises(ConfigError, match=error) as exc_info:
        EnvironmentStore(path).load()

    assert str(path) in str(exc_info.value)


def test_environment_store_write_enforces_private_permissions(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)
    path.chmod(0o644)

    EnvironmentStore(path).select_profile("agency")

    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_environment_store_uses_atomic_replace_in_destination_directory(
    tmp_path, monkeypatch
):
    path = tmp_path / "nested" / "environments.yaml"
    path.parent.mkdir()
    path.write_text(ENVIRONMENTS_YAML)
    observed = {}
    real_replace = os.replace

    def observe_replace(source, destination):
        source_path = Path(source)
        observed["source"] = source_path
        observed["destination"] = Path(destination)
        observed["source_exists"] = source_path.exists()
        observed["source_mode"] = source_path.stat().st_mode & 0o777
        real_replace(source, destination)

    monkeypatch.setattr("meta_cli.environments.os.replace", observe_replace)

    EnvironmentStore(path).select_profile("agency")

    assert observed["source"].parent == path.parent
    assert observed["destination"] == path
    assert observed["source_exists"] is True
    if os.name == "posix":
        assert observed["source_mode"] == 0o600
    assert not observed["source"].exists()
    assert EnvironmentStore(path).active_profile_name() == "agency"


def test_environment_store_failed_atomic_replace_preserves_file_and_cleans_temp(
    tmp_path, monkeypatch
):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)
    original = path.read_text()

    def fail_replace(_source, _destination):
        raise OSError("fixture failure")

    monkeypatch.setattr("meta_cli.environments.os.replace", fail_replace)

    with pytest.raises(ConfigError, match="Unable to write environments file"):
        EnvironmentStore(path).select_profile("agency")

    assert path.read_text() == original
    assert list(tmp_path.glob(".environments.yaml.*.tmp")) == []


def test_environment_config_secret_values_are_redacted(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)

    profile = EnvironmentStore(path).get_profile("agency")

    representation = repr(profile)
    assert "agency-token" not in representation
    assert "agency-secret" not in representation


def test_environment_config_validation_error_does_not_expose_secrets(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(
        """
profiles:
  broken:
    access_token: very-sensitive-token
    app_id: app
    app_secret: very-sensitive-secret
    ad_account_id: invalid
""".strip()
    )

    with pytest.raises(ConfigError) as exc_info:
        EnvironmentStore(path).load()

    assert "very-sensitive-token" not in str(exc_info.value)
    assert "very-sensitive-secret" not in str(exc_info.value)
    assert exc_info.value.__context__ is None


def test_environment_config_model_validation_errors_hide_secret_inputs():
    with pytest.raises(ValueError) as exc_info:
        EnvironmentsFile.model_validate(
            {
                "active_profile": "missing",
                "profiles": {
                    "valid": {
                        "access_token": "direct-sensitive-token",
                        "app_id": "app",
                        "app_secret": "direct-sensitive-secret",
                        "ad_account_id": "invalid",
                    }
                },
            }
        )

    representation = str(exc_info.value)
    assert "direct-sensitive-token" not in representation
    assert "direct-sensitive-secret" not in representation


def test_environment_store_reports_stale_active_profile_safely(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(f"active_profile: missing\n{ENVIRONMENTS_YAML}\n")

    with pytest.raises(ConfigError, match="no longer exists"):
        EnvironmentStore(path).get_active_profile()


def test_environment_config_path_resolution(monkeypatch, tmp_path):
    override = tmp_path / "override.yaml"
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(override))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert environments_file_path() == override

    monkeypatch.delenv("META_CLI_ENVIRONMENTS_FILE")
    assert environments_file_path() == tmp_path / "xdg" / "meta-ads-cli" / "environments.yaml"

    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "home")
    assert environments_file_path() == tmp_path / "home" / ".config/meta-ads-cli/environments.yaml"

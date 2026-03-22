from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path("scripts/generate_brew_formula.py")
    spec = importlib.util.spec_from_file_location("generate_brew_formula", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_requirements_lock(tmp_path):
    mod = _load_module()
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        """
# generated
aiohttp==3.13.3
# via something
-r base.txt
requests==2.32.5
""".strip()
    )

    parsed = mod.parse_requirements_lock(lock)

    assert [item.name for item in parsed] == ["aiohttp", "requests"]
    assert [item.version for item in parsed] == ["3.13.3", "2.32.5"]


def test_formula_class_name():
    mod = _load_module()
    assert mod.formula_class_name("meta-ads-cli") == "MetaAdsCli"


def test_render_formula_contains_resources():
    mod = _load_module()
    resources = [
        mod.Resource(name="requests", url="https://example.com/requests.tar.gz", sha256="abc123"),
        mod.Resource(name="rich", url="https://example.com/rich.tar.gz", sha256="def456"),
    ]

    formula = mod.render_formula(
        formula_name="meta-ads-cli",
        description="CLI",
        homepage="https://example.com",
        source_url="https://example.com/src.tar.gz",
        source_sha256="sourcehash",
        license_name="MIT",
        python_formula="python@3.12",
        resources=resources,
        build_dependencies=['depends_on "rust" => :build'],
    )

    assert "class MetaAdsCli < Formula" in formula
    assert 'resource "requests" do' in formula
    assert 'resource "rich" do' in formula
    assert 'depends_on "python@3.12"' in formula
    assert 'depends_on "rust" => :build' in formula


def test_detect_build_dependencies_for_pydantic_core():
    mod = _load_module()
    reqs = [
        mod.Requirement(name="pydantic-core", version="2.41.5"),
        mod.Requirement(name="rich", version="14.3.3"),
    ]
    deps = mod.detect_build_dependencies(reqs)
    assert 'depends_on "rust" => :build' in deps

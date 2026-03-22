#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.request import urlopen

RUST_BUILD_PACKAGES = {
    "pydantic-core",
}


@dataclass
class Requirement:
    name: str
    version: str


@dataclass
class Resource:
    name: str
    url: str
    sha256: str


def normalize_package_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def parse_requirements_lock(path: Path) -> list[Requirement]:
    requirements: list[Requirement] = []
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-"):
            continue
        if "==" not in line:
            continue

        name, version = line.split("==", 1)
        name = name.strip()
        version = version.strip()
        if not name or not version:
            continue
        requirements.append(Requirement(name=name, version=version))
    return requirements


def fetch_pypi_resource(requirement: Requirement) -> Resource:
    metadata_url = f"https://pypi.org/pypi/{requirement.name}/{requirement.version}/json"
    with urlopen(metadata_url) as response:  # noqa: S310
        payload = json.load(response)

    urls = payload.get("urls", [])
    source_dist = next((item for item in urls if item.get("packagetype") == "sdist"), None)
    if source_dist is None:
        raise RuntimeError(f"No sdist artifact found for {requirement.name}=={requirement.version}")

    return Resource(
        name=requirement.name,
        url=source_dist["url"],
        sha256=source_dist["digests"]["sha256"],
    )


def formula_class_name(formula_name: str) -> str:
    return "".join(part.capitalize() for part in formula_name.replace("_", "-").split("-"))


def detect_build_dependencies(requirements: list[Requirement]) -> list[str]:
    normalized = {normalize_package_name(req.name) for req in requirements}
    build_dependencies: list[str] = []
    if normalized.intersection(RUST_BUILD_PACKAGES):
        build_dependencies.append('depends_on "rust" => :build')
    return build_dependencies


def render_formula(
    formula_name: str,
    description: str,
    homepage: str,
    source_url: str,
    source_sha256: str,
    license_name: str,
    python_formula: str,
    resources: Iterable[Resource],
    build_dependencies: Iterable[str] | None = None,
) -> str:
    class_name = formula_class_name(formula_name)
    dependency_lines = [f'  depends_on "{python_formula}"']
    if build_dependencies:
        dependency_lines.extend([f"  {line}" if not line.startswith("  ") else line for line in build_dependencies])
    dependency_block = "\n".join(dependency_lines)

    resource_blocks = "\n\n".join(
        [
            "\n".join(
                [
                    f"  resource \"{resource.name}\" do",
                    f"    url \"{resource.url}\"",
                    f"    sha256 \"{resource.sha256}\"",
                    "  end",
                ]
            )
            for resource in resources
        ]
    )

    return f'''class {class_name} < Formula
  include Language::Python::Virtualenv

  desc "{description}"
  homepage "{homepage}"
  url "{source_url}"
  sha256 "{source_sha256}"
  license "{license_name}"

{dependency_block}

{resource_blocks}

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "Meta Ads management CLI", shell_output("#{{bin}}/meta-cli --help")
  end
end
'''


def build_formula(
    formula_name: str,
    description: str,
    homepage: str,
    source_url: str,
    source_sha256: str,
    license_name: str,
    python_formula: str,
    requirements_lock: Path,
) -> str:
    requirements = parse_requirements_lock(requirements_lock)
    resources = [fetch_pypi_resource(req) for req in requirements]
    build_dependencies = detect_build_dependencies(requirements)
    return render_formula(
        formula_name=formula_name,
        description=description,
        homepage=homepage,
        source_url=source_url,
        source_sha256=source_sha256,
        license_name=license_name,
        python_formula=python_formula,
        resources=resources,
        build_dependencies=build_dependencies,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Homebrew formula from lockfile")
    parser.add_argument("--formula-name", default="meta-ads-cli")
    parser.add_argument("--description", default="Production-grade CLI for Meta Ads management")
    parser.add_argument("--homepage", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--license", default="MIT", dest="license_name")
    parser.add_argument("--python-formula", default="python@3.12")
    parser.add_argument("--requirements-lock", default="requirements.lock")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    formula = build_formula(
        formula_name=args.formula_name,
        description=args.description,
        homepage=args.homepage,
        source_url=args.source_url,
        source_sha256=args.source_sha256,
        license_name=args.license_name,
        python_formula=args.python_formula,
        requirements_lock=Path(args.requirements_lock),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(formula)
    print(f"Wrote formula to {output_path}")


if __name__ == "__main__":
    main()

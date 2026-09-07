#!/usr/bin/env python3
"""
Extract project dependencies from pyproject.toml, requirements.txt, setup.py, Pipfile.
Outputs to data/rs2zig/dependency.csv
"""

import os
import csv
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "rs2zig")
OUTPUT_CSV = os.path.join(DATA_DIR, "dependency.csv")

def parse_requirements_txt(filepath: str) -> list:
    """Parse standard requirements.txt file for dependency packages and versions."""
    deps = []
    rel_path = os.path.relpath(filepath, PROJECT_ROOT)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                match = re.match(r"^([a-zA-Z0-9_\-\.]+)\s*([<>=!~^].*)?$", line)
                if match:
                    pkg = match.group(1)
                    ver = match.group(2) or "any"
                    deps.append({"package": pkg, "version": ver.strip(), "source_file": rel_path})
    return deps

def parse_pyproject_toml(filepath: str) -> list:
    """Parse pyproject.toml file for project dependencies."""
    deps = []
    rel_path = os.path.relpath(filepath, PROJECT_ROOT)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        in_deps = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("dependencies = [") or line.startswith("dependencies=["):
                in_deps = True
                continue
            if in_deps:
                if line.startswith("]"):
                    in_deps = False
                    continue
                match = re.search(r"[\"']([a-zA-Z0-9_\-\.]+)\s*([<>=!~^].*)?[\"']", line)
                if match:
                    pkg = match.group(1)
                    ver = match.group(2) or "any"
                    deps.append({"package": pkg, "version": ver.strip(), "source_file": rel_path})
    return deps

def main() -> None:
    """Main extraction routine for Python project package dependencies."""
    os.makedirs(DATA_DIR, exist_ok=True)
    deps = []

    req_path = os.path.join(PROJECT_ROOT, "requirements.txt")
    if os.path.exists(req_path):
        deps.extend(parse_requirements_txt(req_path))

    pyproject_path = os.path.join(PROJECT_ROOT, "pyproject.toml")
    if os.path.exists(pyproject_path):
        deps.extend(parse_pyproject_toml(pyproject_path))

    deps.sort(key=lambda x: (x["source_file"], x["package"]))

    fieldnames = ["package", "version", "source_file"]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deps)

    print(f"[find_dependencies] Wrote {len(deps)} dependencies to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()

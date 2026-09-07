#!/usr/bin/env python3
"""
Extract metadata for all Python source files in the repository.
Outputs to data/rs2zig/file.csv
"""

import os
import csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "rs2zig")
OUTPUT_CSV = os.path.join(DATA_DIR, "file.csv")

EXCLUDE_DIRS = {
    ".git", "venv", ".venv", "__pycache__", "data", ".agents",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "build", "dist"
}

def get_module_path(rel_path: str) -> str:
    """Convert relative file path into a Python module dot-notation path."""
    if rel_path.endswith(".py"):
        rel = rel_path[:-3]
    else:
        rel = rel_path
    parts = rel.split(os.sep)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts else "."

def main() -> None:
    """Main extraction routine for Python file metadata."""
    os.makedirs(DATA_DIR, exist_ok=True)
    files_data = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]
        for file in files:
            if file.endswith(".py"):
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PROJECT_ROOT)

                size_bytes = os.path.getsize(abs_path)
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        line_count = sum(1 for _ in f)
                except Exception:
                    line_count = 0

                module = get_module_path(rel_path)
                files_data.append({
                    "file_path": rel_path,
                    "module": module,
                    "line_count": line_count,
                    "size_bytes": size_bytes
                })

    files_data.sort(key=lambda x: x["file_path"])

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path", "module", "line_count", "size_bytes"])
        writer.writeheader()
        writer.writerows(files_data)

    print(f"[find_files] Wrote {len(files_data)} files to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Extract roadmap tasks, bug fix items, and TODO comments across the repository.
Outputs to data/rs2zig/fix_roadmap.csv
"""

import os
import csv
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "rs2zig")
FIX_DIR = os.path.join(PROJECT_ROOT, "data", "fix")
OUTPUT_CSV = os.path.join(DATA_DIR, "fix_roadmap.csv")

EXCLUDE_DIRS = {
    ".git", "venv", ".venv", "__pycache__", "data", ".agents",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "build", "dist"
}

def scan_fix_dir() -> list:
    """Scan data/fix/*.txt for roadmap items and task backlogs."""
    items = []
    if os.path.exists(FIX_DIR):
        for file in os.listdir(FIX_DIR):
            if file.endswith(".txt") or file.endswith(".md"):
                filepath = os.path.join(FIX_DIR, file)
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for idx, line in enumerate(f, 1):
                        line = line.strip()
                        if line and not line.startswith("#"):
                            items.append({
                                "file_path": rel_path,
                                "task_id": f"FIX-{idx:03d}",
                                "category": "ROADMAP",
                                "description": line[:150],
                                "line_number": idx
                            })
    return items

def scan_todo_comments() -> list:
    """Scan Python source files for inline TODO, FIXME, FIX, or HACK comments."""
    items = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]
        for file in files:
            if file.endswith(".py"):
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        for idx, line in enumerate(f, 1):
                            match = re.search(r"#\s*(TODO|FIXME|FIX|HACK)\b\s*:?\s*(.*)", line, re.IGNORECASE)
                            if match:
                                tag = match.group(1).upper()
                                desc = match.group(2).strip() or "Unspecified task"
                                items.append({
                                    "file_path": rel_path,
                                    "task_id": f"{tag}-{idx}",
                                    "category": tag,
                                    "description": desc[:150],
                                    "line_number": idx
                                })
                except Exception:
                    pass
    return items

def main() -> None:
    """Main extraction routine for roadmap tasks and TODO comments."""
    os.makedirs(DATA_DIR, exist_ok=True)
    items = scan_fix_dir() + scan_todo_comments()
    items.sort(key=lambda x: (x["file_path"], x["line_number"]))

    fieldnames = ["file_path", "task_id", "category", "description", "line_number"]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)

    print(f"[find_fix_roadmap] Wrote {len(items)} roadmap/todo items to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()

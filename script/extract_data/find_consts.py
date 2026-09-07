#!/usr/bin/env python3
"""
Extract module-level constants and variables using Python AST.
Outputs to data/rs2zig/const.csv
"""

import os
import csv
import ast

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "rs2zig")
OUTPUT_CSV = os.path.join(DATA_DIR, "const.csv")

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

def process_file(abs_path: str, rel_path: str) -> list:
    """Parse module-level assignments and constant definitions using AST."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        tree = ast.parse(code, filename=abs_path)
        module = get_module_path(rel_path)
        consts = []

        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        if name.isupper() or not name.startswith("_"):
                            val_str = ""
                            try:
                                val_str = ast.unparse(stmt.value)
                            except Exception:
                                pass
                            consts.append({
                                "file_path": rel_path,
                                "module": module,
                                "const_name": name,
                                "value_repr": val_str[:100],
                                "line_number": getattr(stmt, "lineno", 0)
                            })
            elif isinstance(stmt, ast.AnnAssign):
                if isinstance(stmt.target, ast.Name):
                    name = stmt.target.id
                    val_str = ""
                    if stmt.value:
                        try:
                            val_str = ast.unparse(stmt.value)
                        except Exception:
                            pass
                    consts.append({
                        "file_path": rel_path,
                        "module": module,
                        "const_name": name,
                        "value_repr": val_str[:100],
                        "line_number": getattr(stmt, "lineno", 0)
                    })
        return consts
    except Exception:
        return []

def main() -> None:
    """Main extraction routine for module-level constants and variables."""
    os.makedirs(DATA_DIR, exist_ok=True)
    all_consts = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]
        for file in files:
            if file.endswith(".py"):
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
                all_consts.extend(process_file(abs_path, rel_path))

    all_consts.sort(key=lambda x: (x["file_path"], x["line_number"]))

    fieldnames = ["file_path", "module", "const_name", "value_repr", "line_number"]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_consts)

    print(f"[find_consts] Wrote {len(all_consts)} constants to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()

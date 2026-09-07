#!/usr/bin/env python3
"""
Extract module imports across all Python source files using AST.
Outputs to data/rs2zig/import.csv
"""

import os
import csv
import ast

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "rs2zig")
OUTPUT_CSV = os.path.join(DATA_DIR, "import.csv")

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
    """Parse single Python file AST to extract all import and import-from statements."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        tree = ast.parse(code, filename=abs_path)
        module = get_module_path(rel_path)
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "file_path": rel_path,
                        "module": module,
                        "imported_module": alias.name,
                        "imported_symbol": "",
                        "alias": alias.asname or "",
                        "line_number": getattr(node, "lineno", 0)
                    })
            elif isinstance(node, ast.ImportFrom):
                imp_mod = node.module or ""
                if node.level > 0:
                    imp_mod = "." * node.level + imp_mod
                for alias in node.names:
                    imports.append({
                        "file_path": rel_path,
                        "module": module,
                        "imported_module": imp_mod,
                        "imported_symbol": alias.name,
                        "alias": alias.asname or "",
                        "line_number": getattr(node, "lineno", 0)
                    })
        return imports
    except Exception:
        return []

def main() -> None:
    """Main extraction routine for Python module imports metadata."""
    os.makedirs(DATA_DIR, exist_ok=True)
    all_imports = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]
        for file in files:
            if file.endswith(".py"):
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
                all_imports.extend(process_file(abs_path, rel_path))

    all_imports.sort(key=lambda x: (x["file_path"], x["line_number"]))

    fieldnames = ["file_path", "module", "imported_module", "imported_symbol", "alias", "line_number"]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_imports)

    print(f"[find_imports] Wrote {len(all_imports)} imports to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()

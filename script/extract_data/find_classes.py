#!/usr/bin/env python3
"""
Extract metadata for all Python class definitions using Python AST.
Outputs to data/rs2zig/class.csv
"""

import os
import csv
import ast

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "rs2zig")
OUTPUT_CSV = os.path.join(DATA_DIR, "class.csv")

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

class ClassVisitor(ast.NodeVisitor):
    """AST NodeVisitor to collect Python class definitions."""
    def __init__(self, rel_path: str, module: str):
        self.rel_path = rel_path
        self.module = module
        self.classes = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract metadata from class definition node."""
        base_classes = []
        for base in node.bases:
            try:
                base_classes.append(ast.unparse(base))
            except Exception:
                pass

        methods_count = sum(1 for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)))

        decorators = []
        for dec in node.decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except Exception:
                pass

        docstring = ast.get_docstring(node) or ""
        docstring_short = docstring.strip().split("\n")[0] if docstring else ""

        start_line = getattr(node, "lineno", 0)
        end_line = getattr(node, "end_lineno", start_line)

        self.classes.append({
            "file_path": self.rel_path,
            "module": self.module,
            "class_name": node.name,
            "base_classes": ", ".join(base_classes),
            "methods_count": methods_count,
            "decorators": ", ".join(decorators),
            "docstring": docstring_short,
            "start_line": start_line,
            "end_line": end_line,
        })

        self.generic_visit(node)

def process_file(abs_path: str, rel_path: str) -> list:
    """Parse single Python file AST and extract all class definitions."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        tree = ast.parse(code, filename=abs_path)
        module = get_module_path(rel_path)
        visitor = ClassVisitor(rel_path, module)
        visitor.visit(tree)
        return visitor.classes
    except Exception:
        return []

def main() -> None:
    """Main extraction routine for Python class definitions metadata."""
    os.makedirs(DATA_DIR, exist_ok=True)
    all_classes = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]
        for file in files:
            if file.endswith(".py"):
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
                all_classes.extend(process_file(abs_path, rel_path))

    all_classes.sort(key=lambda x: (x["file_path"], x["start_line"]))

    fieldnames = [
        "file_path", "module", "class_name", "base_classes", "methods_count",
        "decorators", "docstring", "start_line", "end_line"
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_classes)

    print(f"[find_classes] Wrote {len(all_classes)} classes to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()

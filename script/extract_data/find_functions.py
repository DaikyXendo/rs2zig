#!/usr/bin/env python3
"""
Extract metadata for all Python functions and methods using Python AST.
Outputs to data/rs2zig/function.csv
"""

import os
import csv
import ast

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "rs2zig")
OUTPUT_CSV = os.path.join(DATA_DIR, "function.csv")

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

def format_arg(arg: ast.arg, default_val=None) -> str:
    """Format single AST argument node with type annotation and default value."""
    s = arg.arg
    if arg.annotation:
        try:
            s += f": {ast.unparse(arg.annotation)}"
        except Exception:
            pass
    if default_val:
        try:
            s += f" = {ast.unparse(default_val)}"
        except Exception:
            s += " = ..."
    return s

def build_args_sig(node: ast.FunctionDef) -> str:
    """Format complete AST function arguments signature string."""
    args_list = []
    num_defaults = len(node.args.defaults)
    pos_without_defaults = len(node.args.args) - num_defaults

    for i, arg in enumerate(node.args.args):
        default = None
        if i >= pos_without_defaults:
            default = node.args.defaults[i - pos_without_defaults]
        args_list.append(format_arg(arg, default))

    if node.args.vararg:
        args_list.append(f"*{format_arg(node.args.vararg)}")

    for i, arg in enumerate(node.args.kwonlyargs):
        default = node.args.kw_defaults[i] if i < len(node.args.kw_defaults) else None
        args_list.append(format_arg(arg, default))

    if node.args.kwarg:
        args_list.append(f"**{format_arg(node.args.kwarg)}")

    return f"({', '.join(args_list)})"

class FunctionVisitor(ast.NodeVisitor):
    """AST NodeVisitor to collect functions and class methods."""
    def __init__(self, rel_path: str, module: str):
        self.rel_path = rel_path
        self.module = module
        self.functions = []
        self.class_stack = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track current enclosing class hierarchy when visiting class nodes."""
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def _visit_func(self, node, is_async: bool = False) -> None:
        """Extract metadata details from FunctionDef or AsyncFunctionDef nodes."""
        if self.class_stack:
            prefix = ".".join(self.class_stack) + "."
            is_method = True
        else:
            prefix = ""
            is_method = False

        func_name = prefix + node.name
        args_sig = build_args_sig(node)

        return_type = ""
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except Exception:
                return_type = ""

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

        self.functions.append({
            "file_path": self.rel_path,
            "module": self.module,
            "function_name": func_name,
            "args": args_sig,
            "return_type": return_type,
            "is_async": is_async,
            "is_method": is_method,
            "decorators": ", ".join(decorators),
            "docstring": docstring_short,
            "start_line": start_line,
            "end_line": end_line,
        })

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit standard synchronous function definition."""
        self._visit_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit asynchronous function definition."""
        self._visit_func(node, is_async=True)

def process_file(abs_path: str, rel_path: str) -> list:
    """Parse single Python file AST and extract all functions and methods."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        tree = ast.parse(code, filename=abs_path)
        module = get_module_path(rel_path)
        visitor = FunctionVisitor(rel_path, module)
        visitor.visit(tree)
        return visitor.functions
    except Exception:
        return []

def main() -> None:
    """Main extraction routine for Python functions and methods metadata."""
    os.makedirs(DATA_DIR, exist_ok=True)
    all_functions = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]
        for file in files:
            if file.endswith(".py"):
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
                all_functions.extend(process_file(abs_path, rel_path))

    all_functions.sort(key=lambda x: (x["file_path"], x["start_line"]))

    fieldnames = [
        "file_path", "module", "function_name", "args", "return_type",
        "is_async", "is_method", "decorators", "docstring", "start_line", "end_line"
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_functions)

    print(f"[find_functions] Wrote {len(all_functions)} functions to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()

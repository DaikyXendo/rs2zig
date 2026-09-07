# RS2ZIG Workspace Agent Guidelines & Knowledge Graph System (Understand-Anything)

Welcome to the **rs2zig** project. This project implements a native Rust to Zig code converter/transpiler written in Python, complete with an **Understand-Anything** codebase knowledge graph and rules engine for **Codex**, **Antigravity**, **Gemini CLI**, and other AI agents.

---

## 📚 Codebase Knowledge Base

The repository maintains an up-to-date knowledge graph in `data/rs2zig/`:
- [file.csv](file:///Users/levanthanh/Documents/code/python/rs2zig/data/rs2zig/file.csv): Catalog of all Python project files, line counts, sizes, and module paths.
- [function.csv](file:///Users/levanthanh/Documents/code/python/rs2zig/data/rs2zig/function.csv): Catalog of all functions/methods, signatures, return types, docstrings, and source lines.
- [class.csv](file:///Users/levanthanh/Documents/code/python/rs2zig/data/rs2zig/class.csv): Catalog of all classes, base classes, method counts, docstrings, and source lines.
- [const.csv](file:///Users/levanthanh/Documents/code/python/rs2zig/data/rs2zig/const.csv): Catalog of all module-level constants, variables, and values.
- [dependency.csv](file:///Users/levanthanh/Documents/code/python/rs2zig/data/rs2zig/dependency.csv): Catalog of project package dependencies.
- [import.csv](file:///Users/levanthanh/Documents/code/python/rs2zig/data/rs2zig/import.csv): Catalog of all internal and external imports across the codebase.
- [fix_roadmap.csv](file:///Users/levanthanh/Documents/code/python/rs2zig/data/rs2zig/fix_roadmap.csv): Roadmap tasks, feature backlog, and TODO items.

### 🔍 How to Query Knowledge Graph & Rules
Use the helper script `script/rs2zig_query.py`:
- `python3 script/rs2zig_query.py summary` - Overview of codebase statistics across all CSV catalogs
- `python3 script/rs2zig_query.py search <terms...>` - Fast search across functions, classes, consts, files, dependencies
- `python3 script/rs2zig_query.py audit` - Check rule compliance (files > 800 lines, docstrings, type hints)
- `python3 script/rs2zig_query.py sync` - Re-run `script/extract_data/extract_data.sh` to update CSVs
- `python3 script/rs2zig_query.py rules` - View raw project rules from AGENTS.md

---

## ⚙️ Mandatory Project Rules (AGENTS.md)

1. **Consult CSV Metadata First**: Always check `data/rs2zig/*.csv` or run `python3 script/rs2zig_query.py search <term>` before creating new symbols to avoid duplicate code.
2. **File Size Limit (800 Lines)**: If creating a new file or modifying an existing file such that it exceeds 800 lines, you MUST refactor it into smaller sub-modules/packages.
3. **Type Annotations**: All public functions and methods MUST include Python type hints (`def func(x: int) -> str:`).
4. **Documentation**: All public functions, classes, and modules MUST have a docstring (`""" ... """`) explaining their purpose.
5. **No Silent Exception Swallowing**: Never use bare `except:` or `except Exception: pass` without logging or explaining why errors are ignored.
6. **Knowledge Graph Sync**: After modifying or adding Python source files, run `python3 script/rs2zig_query.py sync` (or `script/extract_data/extract_data.sh`) to re-extract codebase metadata.

---

## 🛠️ Available Agent Skills
- `rs2zig-understand`: Query codebase structure, inspect dependencies, search CSVs, and audit rules.
- `rs2zig-code-extractor`: Re-run extraction scripts in `script/extract_data/` to keep CSVs up to date.

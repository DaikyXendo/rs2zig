# RS2ZIG Workspace Agent Guidelines & Knowledge Graph System (Understand-Anything)

Welcome to the **rs2zig** project. This project implements a native Rust to Zig code converter/transpiler written in Python, complete with an **Understand-Anything** codebase knowledge graph, incremental batch conversion engine for the **aok** Rust vendor library, and rules engine for **Codex**, **Antigravity**, **Gemini CLI**, and other AI agents.

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

## 📈 AOK Incremental Batch Conversion System

The project includes an incremental batch conversion workflow for converting the Rust `aok` vendor codebase (`/Users/levanthanh/Documents/code/rust/aok/vendor`) into Zig (`aok_converted/vendor`) in growing steps of 20 files.

### Tracking CSV Files (Uncommitted)
- [aok_batch_progress.csv](file:///Users/levanthanh/Documents/code/python/rs2zig/data/aok_batch_progress.csv): Batch statistics log (Batch #, timestamp, total files, added files, valid files, failed files, pass %).
- [aok_file_status.csv](file:///Users/levanthanh/Documents/code/python/rs2zig/data/aok_file_status.csv): Per-file conversion and `zig ast-check` validation status (`rs_file`, `zig_file`, `batch_num`, `status`, `error_message`, `last_updated`).
- **CRITICAL RULE**: `data/aok_*.csv` files MUST NOT be committed to git (ignored in `.gitignore`).

### Batch Conversion Commands
- `PYTHONPATH=src ./venv/bin/python script/incremental_batch_convert.py status` - Display summary table of all batch runs.
- `PYTHONPATH=src ./venv/bin/python script/incremental_batch_convert.py run --step 20` - Run next batch step (+20 files), convert all active files, run `zig ast-check`, and log results to CSVs.

### User Directive "Tiếp" (Next) Workflow
Whenever the user inputs **"Tiếp"** (or "Next"), the agent MUST automatically execute the following iterative TDD loop:
1. **Run Next Batch Step**: Run `PYTHONPATH=src ./venv/bin/python script/incremental_batch_convert.py run --step 20`.
2. **Analyze Failure Patterns**: Inspect `data/aok_file_status.csv` for ALL failed files (both old and newly added). Cluster error messages by root cause.
3. **Implement Unit Tests (TDD)**: Add isolated test cases for every new syntax/compilation error pattern in `tests/test_pattern_fixes_part2.py`.
4. **Fix Transpiler Logic**: Implement fixes in `src/rs2zig/backend/zig_emitter.py`, `ast_builder.py`, or lowering passes.
5. **Verify 100% Unit Test Pass**: Run `PYTHONPATH=src ./venv/bin/python -m unittest discover tests` until all tests pass 100%.
6. **Re-run Batch Step**: Re-run `script/incremental_batch_convert.py run --step 20` to verify pass rate increase across the growing batch.
7. **Sync & Audit**: Run `python3 script/rs2zig_query.py sync` and `python3 script/rs2zig_query.py audit` before concluding.

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
- `rs2zig-aok-batch`: Manage incremental aok batch conversion, inspect error logs in `data/aok_file_status.csv`, and execute the TDD fix loop.

---
name: rs2zig-understand
description: Search, query, and audit the rs2zig codebase knowledge graph (data/rs2zig/*.csv) and project rules.
---

# rs2zig Understand Skill

This skill enables AI agents (Codex, Antigravity, Gemini CLI) to navigate, search, and audit the rs2zig codebase (Rust -> Zig converter in Python) using the pre-extracted knowledge graph in `data/rs2zig/*.csv` and enforcement of `AGENTS.md`.

## Usage Instructions

### 1. View Codebase Summary
To get a high-level view of total files, functions, classes, constants, dependencies, imports, and roadmap items:
```bash
python3 script/rs2zig_query.py summary
```

### 2. Search Codebase Metadata
To search for any function, class, constant, file, import, or dependency:
```bash
python3 script/rs2zig_query.py search <keywords...> [options]
```
*Options:*
- `-r`, `--regex`: Enable regex pattern search (e.g. `search -r "parse.*ast"`)
- `-s`, `--case`: Case-sensitive matching (default is case-insensitive)
- `-w`, `--word`: Match whole word only (e.g. `search -w "Function"`)
- `-p`, `--path <folder>`: Filter by path/folder (e.g. `search -p script/extract_data`)
- `-c`, `--cat <catalog>`: Filter by catalog (e.g. `search main -c function,class`)
- `-o`, `--or`: OR mode (match ANY term instead of ALL terms)
- `-l`, `--limit <N>`: Limit results per category

*Examples:*
```bash
python3 script/rs2zig_query.py search "Visitor"
python3 script/rs2zig_query.py search -r "def.*process" -c function
python3 script/rs2zig_query.py search main -w -s -p script
```

### 3. Audit Codebase Rules
To check rule compliance (finding files > 800 lines, public functions missing documentation or type hints):
```bash
python3 script/rs2zig_query.py audit
```

### 4. Direct CSV Access
If needed, inspect the CSV files directly in `data/rs2zig/`:
- `data/rs2zig/file.csv`
- `data/rs2zig/function.csv`
- `data/rs2zig/class.csv`
- `data/rs2zig/const.csv`
- `data/rs2zig/dependency.csv`
- `data/rs2zig/import.csv`
- `data/rs2zig/fix_roadmap.csv`

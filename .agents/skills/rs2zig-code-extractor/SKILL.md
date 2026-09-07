---
name: rs2zig-code-extractor
description: Execute Python extraction scripts to sync and update rs2zig codebase metadata CSV files in data/rs2zig/*.csv.
---

# rs2zig Code Extractor Skill

This skill allows AI agents to trigger the codebase metadata extraction pipeline whenever Python source code files are created, modified, or deleted in the repository.

## Extraction Pipeline

The extraction pipeline consists of the following Python scripts located in `script/extract_data/`:
- `find_files.py` -> updates `data/rs2zig/file.csv`
- `find_functions.py` -> updates `data/rs2zig/function.csv`
- `find_classes.py` -> updates `data/rs2zig/class.csv`
- `find_consts.py` -> updates `data/rs2zig/const.csv`
- `find_dependencies.py` -> updates `data/rs2zig/dependency.csv`
- `find_imports.py` -> updates `data/rs2zig/import.csv`
- `find_fix_roadmap.py` -> updates `data/rs2zig/fix_roadmap.csv`

## Execution Instructions

Run the synchronization helper command:
```bash
python3 script/rs2zig_query.py sync
```
Or execute the master shell script directly:
```bash
bash script/extract_data/extract_data.sh
```

Always execute this skill after implementing new Python features, creating new modules, or refactoring codebase structures.

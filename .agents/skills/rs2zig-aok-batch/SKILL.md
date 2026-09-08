---
name: rs2zig-aok-batch
description: Manage incremental Rust to Zig batch conversions for the aok vendor codebase, track progress in data/aok_*.csv, and execute the TDD fix loop.
---

# rs2zig AOK Batch Conversion & TDD Fix Skill

This skill documents the automated workflow for managing incremental Rust-to-Zig batch conversion for the `aok` vendor codebase (`/Users/levanthanh/Documents/code/rust/aok/vendor`), logging progress to local uncommitted CSVs, and performing systematic TDD fixes.

## Key Files & Paths

- **Conversion Manager Script**: `script/incremental_batch_convert.py`
- **Batch Log CSV**: `data/aok_batch_progress.csv` (Batch #, timestamp, total files, added files, valid files, failed files, pass %)
- **File Status CSV**: `data/aok_file_status.csv` (Per-file status `VALID`/`FAILED`, error message)
- **Rust Source Dir**: `/Users/levanthanh/Documents/code/rust/aok/vendor`
- **Zig Output Dir**: `aok_converted/vendor`
- **TDD Test Suite**: `tests/test_pattern_fixes_part2.py`

## CLI Commands

### 1. View Progress Status
To view the summary table of all batch runs and current pass rate:
```bash
PYTHONPATH=src ./venv/bin/python script/incremental_batch_convert.py status
```

### 2. Run Next Batch Conversion
To advance the conversion working set by 20 files (+20) and run `zig ast-check` validation across all active files:
```bash
PYTHONPATH=src ./venv/bin/python script/incremental_batch_convert.py run --step 20
```

### 3. Analyze Error Patterns from CSV
To parse and cluster failing files from `data/aok_file_status.csv`:
```bash
./venv/bin/python -c "
import csv, re
from collections import Counter

err_counts = Counter()
with open('data/aok_file_status.csv') as f:
    for row in csv.DictReader(f):
        if row['status'] == 'FAILED':
            clean = re.sub(r'/var/folders/[^:]+:\d+:\d+:\s*', '', row['error_message'])
            clean = re.sub(r'/tmp/[^:]+:\d+:\d+:\s*', '', clean)
            first_line = clean.split('\n')[0].strip()
            norm = re.sub(r'\'[^\']+\'', '\'...\'', first_line)
            err_counts[norm] += 1

for err, count in err_counts.most_common(15):
    print(f'[{count:2d} files] {err}')
"
```

## Standard "Tiếp" (Next) Agent Loop

When the user says **"Tiếp"** (or "Next"), execute the following step-by-step loop:

1. **Step Incremental Batch**: Run `PYTHONPATH=src ./venv/bin/python script/incremental_batch_convert.py run --step 20`.
2. **Analyze Failure CSV (Comprehensive)**: Parse `data/aok_file_status.csv` to group ALL error messages across ALL failed files (both old and newly added across all libraries).
3. **Write Unit Tests (TDD)**: For each identified error pattern, write a standalone test case in `tests/test_pattern_fixes_part2.py` or `tests/test_pattern_fixes_part3.py`.
4. **Fix Transpiler**: Update `src/rs2zig/backend/zig_emitter.py`, `expr_emitter.py`, `stmt_emitter.py`, `decl_emitter.py`, `ast_builder.py`, or lowering passes to resolve errors. If any modified file approaches 800 lines (e.g. > 600–700 lines), perform a thorough, comprehensive refactoring by splitting major logical components into distinct sub-modules completely at once (bringing file size < 400 lines). NEVER perform micro-refactoring (trimming a few lines at a time).
5. **Verify 100% Tests Pass**: Run `PYTHONPATH=src ./venv/bin/python -m unittest discover tests`.
6. **Re-run Batch**: Re-run `script/incremental_batch_convert.py run --step 20` to verify pass rate increase.
7. **Sync & Audit**: Run `python3 script/rs2zig_query.py sync` and `python3 script/rs2zig_query.py audit`.

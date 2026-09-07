#!/usr/bin/env python3
"""
rs2zig Query & Knowledge Graph Tool
Custom Understand-Anything helper for the rs2zig project (Rust to Zig converter in Python).
Queries codebase metadata from data/rs2zig/*.csv and enforces project rules.
"""

import sys
import os
import csv
import re
import argparse
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "rs2zig")
RULE_FILE = os.path.join(PROJECT_ROOT, "AGENTS.md")
EXTRACT_SCRIPT = os.path.join(PROJECT_ROOT, "script", "extract_data", "extract_data.sh")

CSV_FILES = {
    "file": os.path.join(DATA_DIR, "file.csv"),
    "function": os.path.join(DATA_DIR, "function.csv"),
    "class": os.path.join(DATA_DIR, "class.csv"),
    "const": os.path.join(DATA_DIR, "const.csv"),
    "dependency": os.path.join(DATA_DIR, "dependency.csv"),
    "import": os.path.join(DATA_DIR, "import.csv"),
    "fix_roadmap": os.path.join(DATA_DIR, "fix_roadmap.csv"),
}

def print_banner(title: str) -> None:
    """Print formatted section header banner."""
    print("=" * 60)
    print(f" {title}")
    print("=" * 60)

def cmd_rules() -> None:
    """Display raw AGENTS.md rules document."""
    print_banner("RS2ZIG PROJECT RULES (AGENTS.md)")
    if os.path.exists(RULE_FILE):
        with open(RULE_FILE, "r", encoding="utf-8", errors="ignore") as f:
            print(f.read())
    else:
        print("Error: AGENTS.md not found!")

def cmd_summary() -> None:
    """Display summary count of items across all CSV metadata catalogs."""
    print_banner("RS2ZIG CODEBASE KNOWLEDGE GRAPH SUMMARY")
    labels = {
        "file": "FILES",
        "function": "FUNCTIONS",
        "class": "CLASSES",
        "const": "CONSTANTS",
        "dependency": "DEPENDENCIES",
        "import": "IMPORTS",
        "fix_roadmap": "ROADMAP / TODOS",
    }
    for key, filepath in CSV_FILES.items():
        label = labels.get(key, key.upper())
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                rows = list(reader)
                count = max(0, len(rows) - 1)
                print(f"  • {label:<17}: {count:,} items ({os.path.basename(filepath)})")
        else:
            print(f"  • {label:<17}: File missing ({filepath})")
    print("-" * 60)

def cmd_search(args_list: list) -> None:
    """Search knowledge graph CSV catalogs matching terms and filters."""
    parser = argparse.ArgumentParser(
        prog="python3 script/rs2zig_query.py search",
        description="Smart Codebase & Knowledge Graph Search Tool for RS2ZIG"
    )
    parser.add_argument("terms", nargs="*", help="Search keywords or regex pattern")
    parser.add_argument("-r", "--regex", action="store_true", help="Enable Python Regular Expression search")
    parser.add_argument("-s", "--case", action="store_true", help="Match case sensitive (default is case-insensitive)")
    parser.add_argument("-w", "--word", action="store_true", help="Match whole word only")
    parser.add_argument("-o", "--or", dest="or_mode", action="store_true", help="Match ANY keyword (OR mode)")
    parser.add_argument("-p", "--path", "--folder", type=str, default="", help="Filter by folder or file path substring")
    parser.add_argument("-c", "--cat", "--csv", type=str, default="", help="Filter by catalog category (e.g. function, class, file)")
    parser.add_argument("-l", "--limit", type=int, default=10, help="Max results to display per catalog (default: 10)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show full detailed row fields")

    try:
        parsed = parser.parse_args(args_list)
    except SystemExit:
        return

    terms = parsed.terms
    if not terms:
        print("Usage: python3 script/rs2zig_query.py search <terms...> [options]")
        print("Options:")
        print("  -r, --regex           Regex pattern search (e.g. -r 'parse.*ast')")
        print("  -s, --case            Match case sensitive (default is case-insensitive)")
        print("  -w, --word            Match whole word only")
        print("  -o, --or              OR mode (matches ANY term instead of ALL terms)")
        print("  -p, --path <folder>   Filter by folder/path (e.g. -p 'script/extract_data')")
        print("  -c, --cat <category>  Filter by catalog (e.g. -c 'function' or -c 'class,file')")
        print("  -l, --limit <N>       Max results per catalog (default: 10)")
        print("  -v, --verbose         Show full detailed row content")
        return

    is_regex = parsed.regex
    match_case = parsed.case
    whole_word = parsed.word
    or_mode = parsed.or_mode
    path_filter = parsed.path if match_case else parsed.path.lower()
    cat_filter = [c.strip().lower() for c in parsed.cat.split(",")] if parsed.cat else []

    compiled_patterns = []
    if is_regex:
        flags = 0 if match_case else re.IGNORECASE
        for t in terms:
            try:
                compiled_patterns.append(re.compile(t, flags))
            except re.error as e:
                print(f"Error compiling regex pattern '{t}': {e}")
                return
    else:
        for t in terms:
            term_str = t if match_case else t.lower()
            if whole_word:
                flags = 0 if match_case else re.IGNORECASE
                pattern = r"\b" + re.escape(t) + r"\b"
                compiled_patterns.append(re.compile(pattern, flags))
            else:
                compiled_patterns.append(term_str)

    def row_matches(row_text: str) -> bool:
        """Check if row content matches compiled search patterns."""
        check_text = row_text if match_case else row_text.lower()
        results = []
        for pat in compiled_patterns:
            if is_regex or whole_word:
                results.append(bool(pat.search(row_text)))
            else:
                results.append(pat in check_text)
        return any(results) if or_mode else all(results)

    print_banner(f"SEARCH RESULTS FOR: {' '.join(terms)}")
    total_found = 0

    for cat_name, filepath in CSV_FILES.items():
        if cat_filter and cat_name.lower() not in cat_filter:
            continue
        if not os.path.exists(filepath):
            continue

        matches = []
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_val = row.get("file_path", row.get("source_file", ""))
                if path_filter and path_filter not in (file_val if match_case else file_val.lower()):
                    continue

                row_str = " ".join(str(v) for v in row.values())
                if row_matches(row_str):
                    matches.append(row)

        if matches:
            total_found += len(matches)
            print(f"\n--- {cat_name.upper()} ({len(matches)} matches, showing top {min(len(matches), parsed.limit)}) ---")
            for m in matches[:parsed.limit]:
                if parsed.verbose:
                    print(dict(m))
                else:
                    if cat_name == "file":
                        print(f"  • {m['file_path']} ({m['line_count']} lines, {m['module']})")
                    elif cat_name == "function":
                        sig = f"{m['function_name']}{m['args']}"
                        ret = f" -> {m['return_type']}" if m.get('return_type') else ""
                        doc = f" | {m['docstring']}" if m.get('docstring') else ""
                        print(f"  • {m['file_path']}:{m['start_line']} -> {sig}{ret}{doc}")
                    elif cat_name == "class":
                        bases = f"({m['base_classes']})" if m.get('base_classes') else ""
                        print(f"  • {m['file_path']}:{m['start_line']} -> class {m['class_name']}{bases} [{m['methods_count']} methods]")
                    elif cat_name == "const":
                        print(f"  • {m['file_path']}:{m['line_number']} -> {m['const_name']} = {m['value_repr']}")
                    elif cat_name == "dependency":
                        print(f"  • {m['package']} {m['version']} ({m['source_file']})")
                    elif cat_name == "import":
                        sym = f".{m['imported_symbol']}" if m.get('imported_symbol') else ""
                        print(f"  • {m['file_path']}:{m['line_number']} -> import {m['imported_module']}{sym}")
                    elif cat_name == "fix_roadmap":
                        print(f"  • {m['file_path']}:{m['line_number']} [{m['category']}] -> {m['description']}")

    print(f"\nTotal matches across codebase: {total_found}")

def cmd_audit() -> None:
    """Audit project code for rule compliance (file size, docstrings, type hints)."""
    print_banner("RS2ZIG RULE COMPLIANCE & CODE AUDIT")
    issues = 0

    # 1. File size limit (> 800 lines)
    file_csv = CSV_FILES["file"]
    if os.path.exists(file_csv):
        with open(file_csv, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lines = int(row["line_count"])
                    if lines > 800:
                        print(f"  ⚠️  [FILE SIZE LIMIT EXCEEDED] {row['file_path']} has {lines} lines (> 800 max). Split into sub-modules.")
                        issues += 1
                except ValueError:
                    pass

    # 2. Functions missing docstrings
    func_csv = CSV_FILES["function"]
    if os.path.exists(func_csv):
        with open(func_csv, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                func_name = row["function_name"]
                if not func_name.startswith("_") and ".__" not in func_name:
                    if not row.get("docstring"):
                        print(f"  💡 [MISSING DOCSTRING] Public function {func_name} in {row['file_path']}:{row['start_line']}")
                        issues += 1

    # 3. Classes missing docstrings
    class_csv = CSV_FILES["class"]
    if os.path.exists(class_csv):
        with open(class_csv, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row["class_name"].startswith("_"):
                    if not row.get("docstring"):
                        print(f"  💡 [MISSING DOCSTRING] Class {row['class_name']} in {row['file_path']}:{row['start_line']}")
                        issues += 1

    if issues == 0:
        print("  ✅ All audit checks passed! Codebase is fully compliant with AGENTS.md rules.")
    else:
        print(f"\nFound {issues} compliance items to review/fix.")

def cmd_sync() -> None:
    """Execute metadata extraction shell script to sync CSVs."""
    print_banner("SYNCHRONIZING KNOWLEDGE GRAPH CSVs")
    if os.path.exists(EXTRACT_SCRIPT):
        res = subprocess.run(["bash", EXTRACT_SCRIPT], cwd=PROJECT_ROOT)
        if res.returncode == 0:
            print("  ✅ Knowledge graph metadata successfully re-extracted!")
        else:
            print("  ❌ Extraction pipeline failed.")
    else:
        print(f"Error: Extraction script not found at {EXTRACT_SCRIPT}")

def main() -> None:
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("rs2zig Query Helper")
        print("Commands:")
        print("  python3 script/rs2zig_query.py summary   - View codebase statistics")
        print("  python3 script/rs2zig_query.py search    - Search knowledge graph")
        print("  python3 script/rs2zig_query.py audit     - Check AGENTS.md rule compliance")
        print("  python3 script/rs2zig_query.py sync      - Re-run extractors & update CSVs")
        print("  python3 script/rs2zig_query.py rules     - Show AGENTS.md project rules")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "rules":
        cmd_rules()
    elif cmd == "summary":
        cmd_summary()
    elif cmd == "search":
        cmd_search(sys.argv[2:])
    elif cmd == "audit":
        cmd_audit()
    elif cmd == "sync":
        cmd_sync()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()

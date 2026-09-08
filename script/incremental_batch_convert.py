"""Incremental batch conversion manager and CSV progress tracker for rs2zig.

Manages step-by-step conversion of Rust crates into Zig in growing batches
of 20 files, logging progress to an uncommitted CSV file.
"""

import os
import csv
import glob
import time
import argparse
import subprocess
from datetime import datetime
from typing import List, Dict, Tuple
from rs2zig.cli import run_transpile
from rs2zig.validate.zig_fmt_check import ZigValidator


def check_zig_file_syntax(file_path: str) -> Tuple[bool, str]:
    """Check syntax of a generated .zig file using ZigValidator."""
    if not os.path.exists(file_path):
        return (False, "File does not exist")
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()
    validator = ZigValidator()
    return validator.check_syntax(code)


CSV_PROGRESS_PATH = "data/aok_batch_progress.csv"
CSV_FILE_STATUS_PATH = "data/aok_file_status.csv"
DEFAULT_STEP_SIZE = 20
VENDOR_RUST_DIR = "/Users/levanthanh/Documents/code/rust/aok/vendor"
OUTPUT_ZIG_DIR = "aok_converted/vendor"


def get_all_rust_files(source_dir: str = VENDOR_RUST_DIR) -> List[str]:
    """Find all Rust source files under the target source directory.

    Args:
        source_dir: Root directory of Rust codebase.

    Returns:
        Sorted list of absolute paths to .rs files.
    """
    pattern = os.path.join(source_dir, "**", "*.rs")
    files = glob.glob(pattern, recursive=True)
    return sorted(files)


def read_progress_csv(csv_path: str = CSV_PROGRESS_PATH) -> List[Dict[str, str]]:
    """Read existing progress entries from tracking CSV file.

    Args:
        csv_path: Path to tracking CSV file.

    Returns:
        List of row dictionaries if file exists, else empty list.
    """
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def init_progress_csv_if_needed(csv_path: str = CSV_PROGRESS_PATH) -> None:
    """Initialize CSV file with header columns if it does not exist.

    Args:
        csv_path: Path to CSV tracking file.
    """
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    if not os.path.exists(csv_path):
        fieldnames = [
            "batch_num",
            "timestamp",
            "total_files",
            "new_files_added",
            "valid_files",
            "failed_files",
            "pass_rate_pct",
            "top_error_patterns",
        ]
        with open(csv_path, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()


def write_batch_record(
    batch_num: int,
    total_files: int,
    new_added: int,
    valid_files: int,
    failed_files: int,
    error_summary: str,
    csv_path: str = CSV_PROGRESS_PATH
) -> None:
    """Append a batch conversion run record to tracking CSV file.

    Args:
        batch_num: Incremental batch run number.
        total_files: Cumulative count of converted Rust files.
        new_added: Number of new files added in this batch.
        valid_files: Number of .zig files passing ast-check.
        failed_files: Number of .zig files failing ast-check.
        error_summary: Short string summary of top error patterns.
        csv_path: Path to tracking CSV file.
    """
    init_progress_csv_if_needed(csv_path)
    pass_rate = round((valid_files / total_files * 100), 2) if total_files > 0 else 0.0
    fieldnames = [
        "batch_num",
        "timestamp",
        "total_files",
        "new_files_added",
        "valid_files",
        "failed_files",
        "pass_rate_pct",
        "top_error_patterns",
    ]
    record = {
        "batch_num": str(batch_num),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": str(total_files),
        "new_files_added": str(new_added),
        "valid_files": str(valid_files),
        "failed_files": str(failed_files),
        "pass_rate_pct": f"{pass_rate:.2f}%",
        "top_error_patterns": error_summary.replace("\n", " | ")[:200],
    }
    with open(csv_path, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow(record)


def write_file_status_records(
    file_records: List[Dict[str, str]],
    csv_path: str = CSV_FILE_STATUS_PATH
) -> None:
    """Save detailed per-file conversion status entries to CSV file.

    Args:
        file_records: List of dictionaries describing per-file conversion outcome.
        csv_path: Path to per-file tracking CSV file.
    """
    fieldnames = [
        "rs_file",
        "zig_file",
        "batch_num",
        "status",
        "error_message",
        "last_updated",
    ]
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in file_records:
            writer.writerow(rec)


def run_batch_conversion(step_size: int = DEFAULT_STEP_SIZE, recheck: bool = False) -> None:
    """Execute incremental batch conversion and validate results with ast-check.

    Args:
        step_size: Number of new files to add per batch.
        recheck: If True, re-check existing working set without adding new files.
    """
    all_rs_files = get_all_rust_files()
    total_available = len(all_rs_files)
    existing_records = read_progress_csv()

    if recheck:
        batch_num = len(existing_records) if existing_records else 1
        target_count = int(existing_records[-1]["total_files"]) if existing_records else step_size
        actual_new = 0
    else:
        batch_num = len(existing_records) + 1
        target_count = batch_num * step_size
        if target_count > total_available:
            target_count = total_available

    files_to_convert = all_rs_files[:target_count]
    if not recheck:
        actual_new = step_size if batch_num == 1 else len(files_to_convert) - (batch_num - 1) * step_size
        if actual_new < 0:
            actual_new = 0

    print("=" * 65)
    print(f" 🚀 RUNNING INCREMENTAL BATCH {batch_num} {'(RECHECK)' if recheck else ''}")
    print(f" Total files in working set: {len(files_to_convert)} / {total_available}")
    print(f" New files added this batch: {actual_new}")
    print("=" * 65)

    valid_count = 0
    failed_count = 0
    error_patterns: Dict[str, int] = {}
    sample_failures: List[Tuple[str, str]] = []
    file_records: List[Dict[str, str]] = []

    for idx, rs_file in enumerate(files_to_convert, 1):
        rel_path = os.path.relpath(rs_file, VENDOR_RUST_DIR)
        zig_rel = os.path.splitext(rel_path)[0] + ".zig"
        out_zig_path = os.path.join(OUTPUT_ZIG_DIR, zig_rel)
        os.makedirs(os.path.dirname(out_zig_path), exist_ok=True)

        err_msg = ""
        is_valid = False
        try:
            run_transpile(rs_file, output_path=out_zig_path, format_code=False, validate=False, expand=False)
            is_valid, err_msg = check_zig_file_syntax(out_zig_path)
            if is_valid:
                valid_count += 1
            else:
                failed_count += 1
                short_err = err_msg.splitlines()[0] if err_msg else "Unknown syntax error"
                error_patterns[short_err] = error_patterns.get(short_err, 0) + 1
                if len(sample_failures) < 5:
                    sample_failures.append((out_zig_path, err_msg[:250]))
        except Exception as ex:
            failed_count += 1
            err_msg = str(ex)
            error_patterns[err_msg] = error_patterns.get(err_msg, 0) + 1

        file_records.append({
            "rs_file": rel_path,
            "zig_file": zig_rel,
            "batch_num": str(batch_num),
            "status": "VALID" if is_valid else "FAILED",
            "error_message": err_msg.splitlines()[0] if (not is_valid and err_msg) else "",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    top_errors = sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:3]
    error_summary = "; ".join(f"{count}x: {err}" for err, count in top_errors) if top_errors else "None"

    write_batch_record(
        batch_num=batch_num,
        total_files=len(files_to_convert),
        new_added=actual_new,
        valid_files=valid_count,
        failed_files=failed_count,
        error_summary=error_summary,
    )
    write_file_status_records(file_records)

    pass_pct = (valid_count / len(files_to_convert) * 100) if files_to_convert else 0.0
    print("\n" + "=" * 65)
    print(f" 📊 BATCH {batch_num} RESULTS {'(RECHECK)' if recheck else ''}")
    print(f" Total Converted: {len(files_to_convert)}")
    print(f" ✅ Valid (ast-check OK): {valid_count} ({pass_pct:.2f}%)")
    print(f" ❌ Failed: {failed_count}")
    print(f" 📄 Logged to: {CSV_PROGRESS_PATH}")
    print("=" * 65)

    if sample_failures:
        print("\n🔍 SAMPLE ERRORS TO FIX IN UNIT TESTS:")
        for path, err in sample_failures:
            print(f"\n--- {path} ---")
            print(err.strip())


def print_status() -> None:
    """Print progress status table from CSV tracking file."""
    records = read_progress_csv()
    if not records:
        print("No batch progress records found in data/aok_batch_progress.csv yet.")
        return

    print("=" * 75)
    print(" 📈 AOK INCREMENTAL BATCH PROGRESS STATUS")
    print("=" * 75)
    print(f"{'Batch':<7}{'Timestamp':<20}{'Total':<8}{'Added':<8}{'Valid':<8}{'Failed':<8}{'Pass %':<10}")
    print("-" * 75)
    for r in records:
        print(
            f"{r['batch_num']:<7}"
            f"{r['timestamp']:<20}"
            f"{r['total_files']:<8}"
            f"{r['new_files_added']:<8}"
            f"{r['valid_files']:<8}"
            f"{r['failed_files']:<8}"
            f"{r['pass_rate_pct']:<10}"
        )
    print("=" * 75)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Incremental batch converter for rs2zig.")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run next incremental batch conversion.")
    run_parser.add_argument("--step", type=int, default=DEFAULT_STEP_SIZE, help="Files per batch step.")
    run_parser.add_argument("--recheck", action="store_true", help="Re-check existing active files without adding new ones.")

    subparsers.add_parser("status", help="Print progress history from CSV file.")

    args = parser.parse_args()

    if args.command == "status":
        print_status()
    else:
        step = getattr(args, "step", DEFAULT_STEP_SIZE)
        recheck = getattr(args, "recheck", False)
        run_batch_conversion(step_size=step, recheck=recheck)


if __name__ == "__main__":
    main()

"""Fast parallel batch recheck script for aok vendor files."""

import os
import csv
import time
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from rs2zig.cli import run_transpile
from rs2zig.validate.zig_fmt_check import ZigValidator

VENDOR_RUST_DIR = "/Users/levanthanh/Documents/code/rust/aok/vendor"
OUTPUT_ZIG_DIR = "aok_converted/vendor"
CSV_PROGRESS_PATH = "data/aok_batch_progress.csv"
CSV_FILE_STATUS_PATH = "data/aok_file_status.csv"


def process_single_file(rel_path: str) -> dict:
    """Transpile and validate a single Rust file."""
    rs_file = os.path.join(VENDOR_RUST_DIR, rel_path)
    zig_rel = os.path.splitext(rel_path)[0] + ".zig"
    out_zig_path = os.path.join(OUTPUT_ZIG_DIR, zig_rel)
    os.makedirs(os.path.dirname(out_zig_path), exist_ok=True)

    err_msg = ""
    is_valid = False
    try:
        runtime_src = os.path.abspath(os.path.join("src", "rs2zig", "runtime", "bevy_ecs_runtime.zig"))
        if os.path.exists(runtime_src):
            shutil.copy(runtime_src, os.path.join(os.path.dirname(out_zig_path), "bevy_ecs_runtime.zig"))
        run_transpile(rs_file, output_path=out_zig_path, format_code=False, validate=False, expand=False)
        validator = ZigValidator()
        with open(out_zig_path, "r", encoding="utf-8") as zf:
            code_str = zf.read()
        is_valid, err_msg = validator.check_syntax(code_str, file_path=out_zig_path)
    except Exception as ex:
        err_msg = str(ex)
        is_valid = False

    first_err = err_msg.splitlines()[0] if (not is_valid and err_msg) else ""
    return {
        "rs_file": rel_path,
        "zig_file": zig_rel,
        "batch_num": "82",
        "status": "VALID" if is_valid else "FAILED",
        "error_message": first_err,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_valid": is_valid,
        "err_msg": err_msg,
    }


def main() -> None:
    """Run parallel recheck across all active files."""
    active_files = []
    with open(CSV_FILE_STATUS_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            active_files.append(row["rs_file"])

    print(f"Rechecking {len(active_files)} active files with process pool...")
    start_t = time.time()
    file_records = []
    valid_count = 0
    failed_count = 0
    error_patterns = {}

    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = [executor.submit(process_single_file, rel_path) for rel_path in active_files]
        for future in as_completed(futures):
            res = future.result()
            file_records.append(res)
            if res["is_valid"]:
                valid_count += 1
            else:
                failed_count += 1
                err_short = res["error_message"] or "Unknown syntax error"
                error_patterns[err_short] = error_patterns.get(err_short, 0) + 1

    elapsed = time.time() - start_t
    pass_pct = (valid_count / len(active_files) * 100) if active_files else 0.0

    print(f"\nFinished parallel recheck in {elapsed:.2f}s!")
    print(f"Total Converted: {len(active_files)}")
    print(f"✅ Valid (ast-check OK): {valid_count} ({pass_pct:.2f}%)")
    print(f"❌ Failed: {failed_count}")

    # Write updated file status records
    status_fieldnames = ["rs_file", "zig_file", "batch_num", "status", "error_message", "last_updated"]
    clean_records = [{k: r[k] for k in status_fieldnames} for r in file_records]
    clean_records.sort(key=lambda x: x["rs_file"])
    with open(CSV_FILE_STATUS_PATH, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=status_fieldnames)
        writer.writeheader()
        writer.writerows(clean_records)

    # Append progress record
    top_errors = sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:3]
    error_summary = "; ".join(f"{count}x: {err}" for err, count in top_errors) if top_errors else "None"
    progress_fieldnames = [
        "batch_num",
        "timestamp",
        "total_files",
        "new_files_added",
        "valid_files",
        "failed_files",
        "pass_rate_pct",
        "top_error_patterns",
    ]

    progress_record = {
        "batch_num": "82",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": str(len(active_files)),
        "new_files_added": "0",
        "valid_files": str(valid_count),
        "failed_files": str(failed_count),
        "pass_rate_pct": f"{pass_pct:.2f}%",
        "top_error_patterns": error_summary,
    }
    with open(CSV_PROGRESS_PATH, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=progress_fieldnames)
        writer.writerow(progress_record)

    print("Updated CSV progress files!")


if __name__ == "__main__":
    main()

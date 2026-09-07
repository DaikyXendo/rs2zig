#!/usr/bin/env python3
"""
Batch Vendor Transpiler for rs2zig (Phase 2).

Transpiles all 800+ external Rust dependency crates in aok/vendor into aok_converted/vendor/.
"""

import os
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add src to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from rs2zig.frontend.mod_resolver import ModuleResolver
from rs2zig.validate.conversion_reporter import ConversionReporter
from rs2zig.cli import _transpile_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("convert_all_vendor")

VENDOR_DIR = "/Users/levanthanh/Documents/code/rust/aok/vendor"
OUTPUT_VENDOR_DIR = "/Users/levanthanh/Documents/code/python/rs2zig/aok_converted/vendor"

def main() -> None:
    """Execute multithreaded batch transpilation across all vendored dependency crates."""
    if not os.path.exists(VENDOR_DIR):
        logger.error("Vendor directory not found: %s", VENDOR_DIR)
        sys.exit(1)

    os.makedirs(OUTPUT_VENDOR_DIR, exist_ok=True)
    crate_dirs = [os.path.join(VENDOR_DIR, d) for d in os.listdir(VENDOR_DIR) if os.path.isdir(os.path.join(VENDOR_DIR, d))]
    
    logger.info("Found %d vendored crate directories in %s", len(crate_dirs), VENDOR_DIR)

    resolver = ModuleResolver()
    tasks = []
    total_rs_files = 0

    for cdir in crate_dirs:
        cname = os.path.basename(cdir)
        out_cdir = os.path.join(OUTPUT_VENDOR_DIR, cname)
        rs_files = resolver.discover_project_files(cdir)
        total_rs_files += len(rs_files)
        for rs_file in rs_files:
            rel_path = os.path.relpath(rs_file, cdir)
            zig_rel_path = os.path.splitext(rel_path)[0] + ".zig"
            target_out = os.path.join(out_cdir, zig_rel_path)
            tasks.append((rs_file, target_out))

    logger.info("Collected %d total Rust source files across %d crates.", total_rs_files, len(crate_dirs))
    logger.info("Starting multithreaded batch transpilation across 16 worker threads...")

    reporter = ConversionReporter(project_name="aok_vendor_deps")
    start_time = time.time()
    succeeded_count = 0
    failed_count = 0

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(_transpile_worker, t): t for t in tasks}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            if completed % 1000 == 0 or completed == len(tasks):
                logger.info("Progress: %d / %d files processed (%.1f%%)...", completed, len(tasks), (completed / len(tasks)) * 100)
            try:
                rs_file, target_out, success, line_count, err_msg = future.result()
                reporter.add_file_result(rs_file, target_out, success, line_count, err_msg)
                if success:
                    succeeded_count += 1
                else:
                    failed_count += 1
            except Exception as err:
                failed_count += 1
                logger.warning("Worker error: %s", err)

    elapsed = time.time() - start_time
    summary = reporter.print_cli_summary()
    report_json_path = os.path.join(OUTPUT_VENDOR_DIR, "conversion_report.json")
    report_md_path = os.path.join(OUTPUT_VENDOR_DIR, "conversion_report.md")
    reporter.save_reports(report_json_path, report_md_path)

    logger.info("Batch conversion complete in %.2fs. Succeeded: %d, Failed: %d", elapsed, succeeded_count, failed_count)

if __name__ == "__main__":
    main()

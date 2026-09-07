"""
Conversion Statistics & Diagnostics Reporter for rs2zig.

Tracks transpilation success/failure metrics, line counts, and categorized error tracebacks for multi-file project conversions.
"""

import os
import json
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("rs2zig.validate.conversion_reporter")


@dataclass
class FileConversionStatus:
    """Status record for a single file transpilation."""
    input_file: str
    output_file: str
    success: bool
    line_count: int = 0
    error_message: Optional[str] = None


@dataclass
class ConversionReport:
    """Aggregate statistics report for project transpilation."""
    project_name: str
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    duration_seconds: float = 0.0
    total_files: int = 0
    succeeded_files: int = 0
    failed_files: int = 0
    success_rate_percent: float = 0.0
    total_lines_transpiled: int = 0
    file_statuses: List[FileConversionStatus] = field(default_factory=list)

    def finalize(self) -> None:
        """Compute summary statistics."""
        self.end_time = time.time()
        self.duration_seconds = round(self.end_time - self.start_time, 2)
        self.total_files = len(self.file_statuses)
        self.succeeded_files = sum(1 for f in self.file_statuses if f.success)
        self.failed_files = self.total_files - self.succeeded_files
        self.success_rate_percent = round((self.succeeded_files / self.total_files * 100.0), 2) if self.total_files > 0 else 0.0
        self.total_lines_transpiled = sum(f.line_count for f in self.file_statuses if f.success)


class ConversionReporter:
    """Reporter engine tracking transpilation run diagnostics."""

    def __init__(self, project_name: str = "project") -> None:
        """Initialize reporter instance."""
        self.report = ConversionReport(project_name=project_name)

    def add_file_result(
        self,
        input_file: str,
        output_file: str,
        success: bool,
        line_count: int = 0,
        error_message: Optional[str] = None
    ) -> None:
        """Record transpilation result for a single file.

        Args:
            input_file: Input Rust file path.
            output_file: Target Zig file path.
            success: Whether transpilation and validation succeeded.
            line_count: Number of source lines transpiled.
            error_message: Optional error message string if failed.
        """
        self.report.file_statuses.append(
            FileConversionStatus(
                input_file=input_file,
                output_file=output_file,
                success=success,
                line_count=line_count,
                error_message=error_message
            )
        )

    def generate_json_report(self) -> str:
        """Return JSON string representation of report."""
        self.report.finalize()
        return json.dumps(asdict(self.report), indent=2)

    def generate_markdown_report(self) -> str:
        """Return Markdown formatted summary of conversion diagnostics."""
        self.report.finalize()
        lines = [
            f"# RS2ZIG Project Transpilation Report: {self.report.project_name}",
            "",
            "## Summary Metrics",
            f"- **Total Files Discovered**: {self.report.total_files}",
            f"- **Successfully Transpiled**: {self.report.succeeded_files} (✅ {self.report.success_rate_percent}%)",
            f"- **Failed Transpilations**: {self.report.failed_files}",
            f"- **Total Lines Transpiled**: {self.report.total_lines_transpiled}",
            f"- **Execution Time**: {self.report.duration_seconds} seconds",
            "",
            "## File Status Breakdown",
            "| File Path | Status | Lines | Diagnostics / Error |",
            "| :--- | :---: | :---: | :--- |"
        ]

        for fs in sorted(self.report.file_statuses, key=lambda x: x.input_file):
            status_icon = "✅ Pass" if fs.success else "❌ Fail"
            clean_err = fs.error_message.replace("\n", " ").replace("|", "/").strip() if fs.error_message else "-"
            if len(clean_err) > 120:
                clean_err = clean_err[:117] + "..."
            err_str = f"`{clean_err}`" if fs.error_message else "-"
            rel_in = os.path.basename(fs.input_file)
            lines.append(f"| `{rel_in}` | {status_icon} | {fs.line_count} | {err_str} |")

        return "\n".join(lines) + "\n"

    def print_cli_summary(self) -> None:
        """Print concise summary statistics to console output."""
        self.report.finalize()
        logger.info("=" * 60)
        logger.info(" RS2ZIG TRANSPILATION SUMMARY REPORT")
        logger.info("=" * 60)
        logger.info("  • Project Name     : %s", self.report.project_name)
        logger.info("  • Total Files      : %d", self.report.total_files)
        logger.info("  • Succeeded Files  : %d (%.1f%%)", self.report.succeeded_files, self.report.success_rate_percent)
        logger.info("  • Failed Files     : %d", self.report.failed_files)
        logger.info("  • Total Source Lines: %d", self.report.total_lines_transpiled)
        logger.info("  • Duration         : %.2fs", self.report.duration_seconds)
        logger.info("=" * 60)

    def save_reports(self, output_dir: str) -> None:
        """Save json and markdown reports into target output directory.

        Args:
            output_dir: Directory path to write reports into.
        """
        abs_out = os.path.abspath(output_dir)
        os.makedirs(abs_out, exist_ok=True)
        json_path = os.path.join(abs_out, "conversion_report.json")
        md_path = os.path.join(abs_out, "conversion_report.md")

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(self.generate_json_report())

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.generate_markdown_report())

        logger.info("Saved conversion reports to %s and %s", json_path, md_path)

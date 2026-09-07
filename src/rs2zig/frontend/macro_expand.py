"""
Macro Expansion Pass for rs2zig.

Provides functionality to expand Rust procedural and declarative macros using `cargo expand`.
"""

import logging
import subprocess
import shutil
from typing import Optional

logger = logging.getLogger("rs2zig.frontend.macro_expand")


def expand_macros(code_or_file: str, is_file_path: bool = False) -> str:
    """Expand macros in Rust source code using cargo expand if available.

    Args:
        code_or_file: Rust source code string or path to a Rust source file.
        is_file_path: True if code_or_file is a filepath, False if it is source code.

    Returns:
        Expanded Rust source code string.
    """
    cargo_bin: Optional[str] = shutil.which("cargo")
    if not cargo_bin:
        logger.warning("Cargo binary not found on PATH. Skipping macro expansion pass.")
        return _read_or_return(code_or_file, is_file_path)

    if not is_file_path:
        # Standalone code string provided, return as is unless running inside a crate
        logger.debug("Source code string provided. Skipping cargo expand for direct snippet.")
        return code_or_file

    try:
        logger.info("Executing `cargo expand` on %s", code_or_file)
        result = subprocess.run(
            [cargo_bin, "expand"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0 and result.stdout:
            logger.info("Macro expansion succeeded.")
            return result.stdout
        else:
            logger.warning(
                "Cargo expand exited with code %d. stderr: %s. Using raw source code.",
                result.returncode,
                result.stderr.strip()
            )
            return _read_or_return(code_or_file, is_file_path)
    except Exception as err:
        logger.error("Failed to run macro expansion: %s. Proceeding with raw source.", err)
        return _read_or_return(code_or_file, is_file_path)


def _read_or_return(code_or_file: str, is_file_path: bool) -> str:
    """Helper to read file content or return code string."""
    if is_file_path:
        try:
            with open(code_or_file, "r", encoding="utf-8") as file_handle:
                return file_handle.read()
        except OSError as err:
            logger.error("Error reading file %s: %s", code_or_file, err)
            raise
    return code_or_file

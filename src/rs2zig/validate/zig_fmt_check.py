"""
Zig Validator and Formatter for rs2zig.

Runs `zig fmt` and `zig ast-check` / `zig build-obj` to validate generated Zig code.
"""

import logging
import subprocess
import shutil
import tempfile
import os
from typing import Tuple, Optional

logger = logging.getLogger("rs2zig.validate.zig_fmt_check")


class ZigValidator:
    """Invokes Zig toolchain to validate generated code syntax and semantics."""

    def __init__(self) -> None:
        """Check availability of Zig compiler binary on system PATH."""
        self.zig_bin: Optional[str] = shutil.which("zig")
        if not self.zig_bin:
            logger.warning("Zig compiler binary not found on PATH. Validation will be skipped.")

    def format_code(self, zig_code: str) -> str:
        """Format Zig code using `zig fmt --stdin`.

        Args:
            zig_code: Input Zig source code string.

        Returns:
            Formatted Zig code string (or original string if zig is absent).
        """
        if not self.zig_bin:
            return zig_code

        try:
            result = subprocess.run(
                [self.zig_bin, "fmt", "--stdin"],
                input=zig_code,
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
            else:
                logger.warning("`zig fmt` failed: %s. Returning raw emitted code.", result.stderr.strip())
                return zig_code
        except Exception as err:
            logger.error("Error executing `zig fmt`: %s", err)
            return zig_code

    def check_syntax(self, zig_code: str) -> Tuple[bool, str]:
        """Validate Zig source code by invoking `zig ast-check` or `zig build-obj`.

        Args:
            zig_code: Input Zig source code string.

        Returns:
            Tuple of (is_valid: bool, error_message: str).
        """
        if not self.zig_bin:
            return (True, "Zig binary not found; syntax check skipped.")

        runtime_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "runtime", "bevy_ecs_runtime.zig"))
        if os.path.exists(runtime_src):
            runtime_dst = os.path.join(tempfile.gettempdir(), "bevy_ecs_runtime.zig")
            if not os.path.exists(runtime_dst):
                shutil.copy(runtime_src, runtime_dst)

        with tempfile.NamedTemporaryFile("w", suffix=".zig", delete=False) as temp_file:
            temp_file.write(zig_code)
            temp_path = temp_file.name

        try:
            # Try zig ast-check first
            ast_res = subprocess.run(
                [self.zig_bin, "ast-check", temp_path],
                capture_output=True,
                text=True,
                check=False
            )
            if ast_res.returncode == 0:
                return (True, "Syntax valid (ast-check passed).")

            # Try zig build-obj as fallback check
            build_res = subprocess.run(
                [self.zig_bin, "build-obj", temp_path, "-fno-emit-bin"],
                capture_output=True,
                text=True,
                check=False
            )
            if build_res.returncode == 0:
                return (True, "Syntax valid (build-obj passed).")
            else:
                return (False, build_res.stderr or ast_res.stderr or "Unknown Zig compilation error.")
        except Exception as err:
            logger.error("Error validating Zig code with compiler: %s", err)
            return (False, str(err))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

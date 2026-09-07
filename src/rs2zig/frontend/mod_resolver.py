"""
Module Resolver for rs2zig.

Handles multi-file Rust projects (mod declarations, directory structures, and Cargo.toml dependency mapping).
"""

import os
import logging
from typing import List, Dict

logger = logging.getLogger("rs2zig.frontend.mod_resolver")


class ModuleResolver:
    """Discovers and resolves sub-modules in multi-file Rust projects."""

    def discover_project_files(self, project_dir: str) -> List[str]:
        """Discover all Rust source files in a project directory.

        Args:
            project_dir: Root directory of Rust project.

        Returns:
            List of absolute paths to .rs files.
        """
        rs_files: List[str] = []
        for root, _, files in os.walk(project_dir):
            for f in files:
                if f.endswith(".rs"):
                    rs_files.append(os.path.join(root, f))
        return rs_files

    def map_rust_mod_to_zig_import(self, mod_name: str) -> str:
        """Map Rust module name to Zig @import statement string.

        Args:
            mod_name: Name of Rust module.

        Returns:
            Zig import string.
        """
        return f'const {mod_name} = @import("{mod_name}.zig");'

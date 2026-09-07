"""
Tree-sitter Parser Wrapper for rs2zig.

Parses Rust source code into a tree-sitter Concrete Syntax Tree (CST).
"""

import logging
from typing import Optional
import tree_sitter
import tree_sitter_rust

logger = logging.getLogger("rs2zig.frontend.ts_parser")


class RustParser:
    """Wrapper class around tree-sitter parser for Rust."""

    def __init__(self) -> None:
        """Initialize tree-sitter Rust parser and language binding."""
        try:
            self._language = tree_sitter.Language(tree_sitter_rust.language())
            self._parser = tree_sitter.Parser(self._language)
            logger.debug("Tree-sitter Rust parser initialized successfully.")
        except Exception as err:
            logger.error("Failed to initialize tree-sitter Rust parser: %s", err)
            raise RuntimeError(f"Tree-sitter initialization error: {err}") from err

    def parse_code(self, code: str) -> tree_sitter.Tree:
        """Parse Rust source code string into tree-sitter Tree.

        Args:
            code: Rust source code string.

        Returns:
            Parsed tree_sitter.Tree object.
        """
        code_bytes = code.encode("utf-8")
        tree = self._parser.parse(code_bytes)
        if tree.root_node.has_error:
            logger.warning("Tree-sitter encountered syntax errors during parsing.")
        return tree

    def parse_file(self, file_path: str) -> tree_sitter.Tree:
        """Parse Rust file into tree-sitter Tree.

        Args:
            file_path: Path to .rs file.

        Returns:
            Parsed tree_sitter.Tree object.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file_handle:
                content = file_handle.read()
            return self.parse_code(content)
        except OSError as err:
            logger.error("Error reading file for parsing %s: %s", file_path, err)
            raise

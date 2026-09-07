"""
Enum and Match Pattern Lowering Pass for rs2zig.

Transforms Rust enums into Zig enums / tagged unions and match expressions into Zig switch statements.
"""

import logging
from rs2zig.ir.nodes import (
    SourceFile,
    EnumDecl,
    MatchExpr,
    MatchArm,
    IdentifierExpr,
    LiteralExpr,
    Expr,
)
from rs2zig.lowering.stdlib_map import map_type

logger = logging.getLogger("rs2zig.lowering.enum_lowering")


class EnumLoweringPass:
    """Pass to process Rust enums and match pattern structures."""

    def is_tagged_union(self, enum_decl: EnumDecl) -> bool:
        """Check if enum decl contains any payload fields requiring a Zig tagged union.

        Args:
            enum_decl: EnumDecl node.

        Returns:
            True if any variant has payload fields, False if simple enum.
        """
        return any(len(variant.fields) > 0 for variant in enum_decl.variants)

    def lower_match_pattern(self, pattern: str) -> str:
        """Convert Rust match arm pattern string to Zig switch arm pattern string.

        Args:
            pattern: Rust pattern string (e.g., '_', '0', 'Some(x)', 'MyEnum::Variant').

        Returns:
            Zig switch arm pattern string (e.g. 'else', '0', '.Variant').
        """
        pattern = pattern.strip()
        if pattern == "_":
            return "else"

        if "::" in pattern:
            parts = pattern.split("::")
            return f".{parts[-1]}"

        return pattern

"""
Plugin API interface for rs2zig Library Lowering Architecture.

Allows external library passes (Bevy, Stdlib, Tokio, Serde) to register lowering rules.
"""

from typing import Optional
from rs2zig.ir.nodes import (
    SourceFile,
    TypeNode,
    Expr,
    CallExpr,
    StructInitExpr,
)


class LibraryLoweringPlugin:
    """Base interface for all library and crate lowering plugins."""

    def crate_name(self) -> str:
        """Return the target crate or library name (e.g. 'bevy', 'std', 'serde')."""
        return "base"

    def lower_type(self, type_node: TypeNode) -> Optional[TypeNode]:
        """Lower a Rust type to target Zig type representation.

        Args:
            type_node: Input TypeNode to transform.

        Returns:
            Transformed TypeNode or None if unchanged.
        """
        return None

    def lower_call(self, expr: CallExpr) -> Optional[Expr]:
        """Lower a function or method call expression.

        Args:
            expr: Input CallExpr to transform.

        Returns:
            Transformed Expr or None if unchanged.
        """
        return None

    def lower_struct_init(self, expr: StructInitExpr) -> Optional[StructInitExpr]:
        """Lower a struct initialization expression.

        Args:
            expr: Input StructInitExpr to transform.

        Returns:
            Transformed StructInitExpr or None if unchanged.
        """
        return None

    def lower_source_file(self, sf: SourceFile) -> bool:
        """Run full source file transformation pass.

        Args:
            sf: SourceFile AST node to mutate.

        Returns:
            True if plugin runtime import is required.
        """
        return False

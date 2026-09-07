"""
Multi-threading & Async Lowering Plugin for rs2zig.

Handles std::thread::spawn, tokio::spawn, and async fn lowering for native Zig std.Thread.
"""

import logging
from typing import Optional
from rs2zig.ir.nodes import (
    SourceFile,
    CallExpr,
    IdentifierExpr,
    FieldAccessExpr,
    Expr,
    LetStmt,
    ExprStmt,
)
from rs2zig.lowering.plugin_api import LibraryLoweringPlugin

logger = logging.getLogger("rs2zig.lowering.async_plugin")


class AsyncPlugin(LibraryLoweringPlugin):
    """Lowering plugin for Rust multithreading and async tasks."""

    def crate_name(self) -> str:
        """Return crate name."""
        return "async"

    def lower_call(self, expr: CallExpr) -> Optional[Expr]:
        """Lower thread spawning calls to Zig std.Thread.spawn.

        Args:
            expr: Input CallExpr node.

        Returns:
            Transformed CallExpr node.
        """
        if isinstance(expr.callee, IdentifierExpr):
            callee_name = expr.callee.name
            if callee_name in ("std::thread::spawn", "thread::spawn", "tokio::spawn"):
                closure_arg = expr.args[0] if expr.args else IdentifierExpr("run")
                expr.callee = FieldAccessExpr(target=IdentifierExpr("std.Thread"), field_name="spawn")
                expr.args = [
                    IdentifierExpr(".{}"),
                    closure_arg,
                    IdentifierExpr(".{}")
                ]
                return expr
        return None

    def lower_source_file(self, sf: SourceFile) -> bool:
        """Traverse SourceFile AST and lower threading/async calls.

        Args:
            sf: SourceFile AST node.

        Returns:
            False as std.Thread is built into stdlib.
        """
        for fn in sf.functions:
            if not fn.body:
                continue

            for stmt in fn.body.stmts:
                if isinstance(stmt, LetStmt) and isinstance(stmt.value, CallExpr):
                    self.lower_call(stmt.value)
                elif isinstance(stmt, ExprStmt) and isinstance(stmt.expr, CallExpr):
                    self.lower_call(stmt.expr)

        return False

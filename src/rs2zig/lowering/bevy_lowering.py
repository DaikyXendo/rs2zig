"""
Bevy Engine API Lowering Pass for rs2zig.

Recognizes Bevy ECS calls (App, World, Component, Startup, Update) and maps them to the native Zig ECS runtime.
"""

import logging
from rs2zig.ir.nodes import (
    SourceFile,
    CallExpr,
    IdentifierExpr,
    FieldAccessExpr,
    LetStmt,
    ExprStmt,
    FnDecl,
)

logger = logging.getLogger("rs2zig.lowering.bevy_lowering")


class BevyLoweringPass:
    """Pass to detect and lower Bevy ECS engine API calls to native Zig ECS runtime calls."""

    def lower_source_file(self, sf: SourceFile) -> bool:
        """Run Bevy ECS lowering pass on SourceFile.

        Args:
            sf: SourceFile AST node to mutate in place.

        Returns:
            True if Bevy ECS runtime import is required.
        """
        bevy_used = False

        for fn in sf.functions:
            if not fn.body:
                continue
            for stmt in fn.body.stmts:
                expr = stmt.value if isinstance(stmt, LetStmt) else (stmt.expr if isinstance(stmt, ExprStmt) else None)
                if isinstance(expr, CallExpr):
                    if self._lower_call_chain(expr):
                        bevy_used = True

        return bevy_used

    def _lower_call_chain(self, expr: CallExpr) -> bool:
        """Recursively lower method chain calls (e.g. App::new().add_systems(...).run()).

        Args:
            expr: CallExpr AST node.

        Returns:
            True if Bevy call detected and lowered.
        """
        is_bevy = False

        if isinstance(expr.callee, FieldAccessExpr):
            # Check inner target expression first
            if isinstance(expr.callee.target, CallExpr):
                if self._lower_call_chain(expr.callee.target):
                    is_bevy = True

            field_name = expr.callee.field_name
            if field_name == "add_systems":
                is_bevy = True
                if len(expr.args) >= 2:
                    expr.args = [expr.args[1]]
                expr.callee.field_name = "add_system"
            elif field_name == "run":
                is_bevy = True

        elif isinstance(expr.callee, IdentifierExpr):
            if expr.callee.name in ("App::new", "bevy::prelude::App::new"):
                is_bevy = True
                expr.callee.name = "bevy_ecs.App.init"
                expr.args = [IdentifierExpr("std.heap.page_allocator")]

        return is_bevy

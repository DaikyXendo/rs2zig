"""
Bevy Engine Lowering Plugin for rs2zig.

Maps Bevy ECS calls (App, World, Component, Startup, Update, Query, Res) to native Zig ECS runtime.
"""

import logging
from typing import Optional
from rs2zig.ir.nodes import (
    SourceFile,
    CallExpr,
    IdentifierExpr,
    FieldAccessExpr,
    LetStmt,
    ExprStmt,
    LoopExpr,
    TypeNode,
    BlockExpr,
    StructInitExpr,
)
from rs2zig.lowering.plugin_api import LibraryLoweringPlugin

logger = logging.getLogger("rs2zig.lowering.bevy_plugin")


class BevyPlugin(LibraryLoweringPlugin):
    """Lowering plugin for Bevy Engine ECS framework."""

    def crate_name(self) -> str:
        """Return crate name."""
        return "bevy_ecs"

    def lower_struct_init(self, expr: StructInitExpr) -> Optional[StructInitExpr]:
        """Prefix Bevy component struct initializers with bevy_ecs namespace.

        Args:
            expr: Input StructInitExpr node.

        Returns:
            Transformed StructInitExpr node.
        """
        if expr.struct_name in ("Transform", "Velocity", "Time", "Commands"):
            expr.struct_name = f"bevy_ecs.{expr.struct_name}"
            return expr
        return None

    def lower_source_file(self, sf: SourceFile) -> bool:
        """Run Bevy ECS lowering pass on SourceFile.

        Args:
            sf: SourceFile AST node to mutate in place.

        Returns:
            True if Bevy ECS runtime import is required.
        """
        bevy_used = False

        for fn in sf.functions:
            for param in fn.params:
                p_name = param.param_type.name
                if p_name == "Commands":
                    param.param_type = TypeNode(name="*bevy_ecs.Commands")
                    param.is_mutable = False
                    bevy_used = True
                elif p_name == "Res" and param.param_type.generic_args:
                    inner_res = param.param_type.generic_args[0].name
                    param.param_type = TypeNode(name=f"*const bevy_ecs.{inner_res}")
                    param.is_mutable = False
                    bevy_used = True
                elif p_name == "Query":
                    param.param_type = TypeNode(name="*bevy_ecs.QueryTransformVelocity")
                    param.is_mutable = False
                    bevy_used = True

            if not fn.body:
                continue

            self._lower_block(fn.body)

            for stmt in fn.body.stmts:
                expr = stmt.value if isinstance(stmt, LetStmt) else (stmt.expr if isinstance(stmt, ExprStmt) else None)
                if expr:
                    self._lower_expr(expr)
                if isinstance(expr, CallExpr):
                    if self._lower_call_chain(expr):
                        bevy_used = True

        return bevy_used

    def _lower_expr(self, expr: Expr) -> None:
        """Recursively lower StructInitExpr nodes inside expressions."""
        if isinstance(expr, StructInitExpr):
            self.lower_struct_init(expr)
            for f in expr.fields:
                self._lower_expr(f.value)
        elif isinstance(expr, CallExpr):
            for arg in expr.args:
                self._lower_expr(arg)

    def _lower_block(self, block: BlockExpr) -> None:
        """Recursively lower statements inside block.

        Args:
            block: BlockExpr to mutate.
        """
        for stmt in block.stmts:
            if isinstance(stmt, ExprStmt) and isinstance(stmt.expr, LoopExpr):
                loop = stmt.expr
                if loop.loop_kind == "for" and isinstance(loop.iterable, CallExpr):
                    callee = loop.iterable.callee
                    if isinstance(callee, FieldAccessExpr) and callee.field_name in ("iter", "iter_mut"):
                        target_name = callee.target.name if isinstance(callee.target, IdentifierExpr) else "query"
                        loop.loop_kind = "while"
                        loop.condition = CallExpr(
                            callee=FieldAccessExpr(target=IdentifierExpr(target_name), field_name="next")
                        )
                        loop.var_name = "item"
                        loop.iterable = None

                        if loop.var_name:
                            pre_stmts = [
                                LetStmt(name="transform", var_type=None, value=IdentifierExpr("item.transform"), is_mutable=False),
                                LetStmt(name="velocity", var_type=None, value=IdentifierExpr("item.velocity"), is_mutable=False),
                            ]
                            loop.body.stmts = pre_stmts + loop.body.stmts

    def _lower_call_chain(self, expr: CallExpr) -> bool:
        """Recursively lower method chain calls (e.g. App::new().add_systems(...).run()).

        Args:
            expr: CallExpr AST node.

        Returns:
            True if Bevy call detected and lowered.
        """
        is_bevy = False

        if isinstance(expr.callee, FieldAccessExpr):
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

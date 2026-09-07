"""
Ownership and Memory Strategy Pass for rs2zig.

Manages heap allocation lowering (Vec, String, Box) and allocator injection.
"""

import logging
from rs2zig.ir.nodes import (
    SourceFile,
    FnDecl,
    Param,
    TypeNode,
    CallExpr,
    IdentifierExpr,
    FieldAccessExpr,
    LetStmt,
    ExprStmt,
    TryExpr,
)

logger = logging.getLogger("rs2zig.lowering.ownership_pass")


class OwnershipPass:
    """Pass to detect allocations, lower Vec/String operations, and inject allocator requirements."""

    def lower_source_file(self, sf: SourceFile) -> None:
        """Run ownership and allocator lowering pass on SourceFile.

        Args:
            sf: SourceFile AST node to mutate in place.
        """
        allocator_funcs = set()

        for fn in sf.functions:
            if self._lower_function(fn):
                allocator_funcs.add(fn.name)

        for impl in sf.impls:
            for fn in impl.methods:
                if self._lower_function(fn):
                    allocator_funcs.add(fn.name)

        # Update callers of allocator functions
        for fn in sf.functions:
            self._update_callers(fn, allocator_funcs)

    def _lower_function(self, fn: FnDecl) -> bool:
        """Lower function body heap calls and inject allocator parameters if needed.

        Returns:
            True if function requires allocator.
        """
        if not fn.body:
            return False

        uses_allocator = False

        for stmt in fn.body.stmts:
            if isinstance(stmt, LetStmt) and isinstance(stmt.value, CallExpr):
                callee_name = str(stmt.value.callee.name) if isinstance(stmt.value.callee, IdentifierExpr) else ""
                if callee_name in ("Vec::new", "Vec::with_capacity"):
                    uses_allocator = True
                    stmt.value = IdentifierExpr("std.ArrayList(i32).empty")
            elif isinstance(stmt, ExprStmt) and isinstance(stmt.expr, CallExpr):
                callee_node = stmt.expr.callee
                if isinstance(callee_node, FieldAccessExpr) and callee_node.field_name == "push":
                    uses_allocator = True
                    callee_node.field_name = "append"
                    stmt.expr.args.insert(0, IdentifierExpr("allocator"))
                    stmt.expr = TryExpr(operand=stmt.expr)

        if uses_allocator:
            if fn.return_type is None or fn.return_type.name == "void":
                fn.return_type = TypeNode(name="!void")
            if fn.name != "main":
                has_alloc = any(p.name == "allocator" for p in fn.params)
                if not has_alloc:
                    fn.params.insert(
                        0,
                        Param(
                            name="allocator",
                            param_type=TypeNode(name="std.mem.Allocator")
                        )
                    )

        return uses_allocator

    def _update_callers(self, fn: FnDecl, allocator_funcs: set) -> None:
        """Pass allocator argument to called functions requiring an allocator."""
        if not fn.body:
            return

        for stmt in fn.body.stmts:
            expr = stmt.value if isinstance(stmt, LetStmt) else (stmt.expr if isinstance(stmt, ExprStmt) else None)
            if isinstance(expr, CallExpr) and isinstance(expr.callee, IdentifierExpr):
                if expr.callee.name in allocator_funcs:
                    alloc_arg = IdentifierExpr("std.heap.page_allocator") if fn.name == "main" else IdentifierExpr("allocator")
                    if not any(isinstance(a, IdentifierExpr) and a.name in ("allocator", "std.heap.page_allocator") for a in expr.args):
                        expr.args.insert(0, alloc_arg)
                    if isinstance(stmt, ExprStmt) and not isinstance(stmt.expr, TryExpr):
                        stmt.expr = TryExpr(operand=stmt.expr)
                        if fn.return_type is None or fn.return_type.name == "void":
                            fn.return_type = TypeNode(name="!void")

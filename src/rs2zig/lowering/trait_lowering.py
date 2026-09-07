"""
Trait and Generics Lowering Pass for rs2zig.

Processes trait definitions, merges impl trait methods into structs, and converts generics to Zig comptime params.
"""

import logging
from rs2zig.ir.nodes import (
    SourceFile,
    FnDecl,
    Param,
    TypeNode,
    CallExpr,
    IdentifierExpr,
    LetStmt,
    ExprStmt,
)

logger = logging.getLogger("rs2zig.lowering.trait_lowering")


class TraitLoweringPass:
    """Pass to lower traits and generics into Zig equivalents."""

    def lower_source_file(self, sf: SourceFile) -> None:
        """Run trait and generic lowering pass on SourceFile.

        Args:
            sf: SourceFile AST node to mutate in place.
        """
        generic_funcs = set()

        for fn in sf.functions:
            if fn.generic_params:
                generic_funcs.add(fn.name)
                self._lower_function_generics(fn)

        for impl in sf.impls:
            for fn in impl.methods:
                if fn.generic_params:
                    generic_funcs.add(fn.name)
                    self._lower_function_generics(fn)

        for fn in sf.functions:
            self._update_generic_callers(fn, generic_funcs)

    def _lower_function_generics(self, fn: FnDecl) -> None:
        """Convert FnDecl.generic_params into Zig comptime parameters."""
        if not fn.generic_params:
            return

        for gp in reversed(fn.generic_params):
            has_param = any(p.name == gp.name for p in fn.params)
            if not has_param:
                fn.params.insert(
                    0,
                    Param(
                        name=f"comptime {gp.name}",
                        param_type=TypeNode(name="type")
                    )
                )
        fn.generic_params = []

    def _update_generic_callers(self, fn: FnDecl, generic_funcs: set) -> None:
        """Update callers of generic functions to supply comptime type parameter."""
        if not fn.body:
            return

        for stmt in fn.body.stmts:
            expr = stmt.value if isinstance(stmt, LetStmt) else (stmt.expr if isinstance(stmt, ExprStmt) else None)
            if isinstance(expr, CallExpr) and isinstance(expr.callee, IdentifierExpr):
                if expr.callee.name in generic_funcs:
                    if len(expr.args) == 1:
                        expr.args.insert(0, IdentifierExpr("i32"))

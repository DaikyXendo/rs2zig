"""
Rust Standard Library Lowering Plugin for rs2zig.

Handles lowering of std collections (HashMap, HashSet), filesystem, path, and system APIs to native Zig.
"""

import logging
from typing import Optional
from rs2zig.ir.nodes import (
    SourceFile,
    TypeNode,
    LetStmt,
    ExprStmt,
    CallExpr,
    IdentifierExpr,
    Expr,
)
from rs2zig.lowering.plugin_api import LibraryLoweringPlugin

logger = logging.getLogger("rs2zig.lowering.stdlib_plugin")


class StdlibPlugin(LibraryLoweringPlugin):
    """Lowering plugin for Rust standard library components."""

    def crate_name(self) -> str:
        """Return crate name."""
        return "std"

    def lower_type(self, type_node: TypeNode) -> Optional[TypeNode]:
        """Lower std collection and system types to Zig equivalents.

        Args:
            type_node: Input TypeNode.

        Returns:
            Transformed TypeNode or None.
        """
        name = type_node.name.strip()
        if name in ("HashMap", "std::collections::HashMap"):
            if type_node.generic_args and len(type_node.generic_args) >= 2:
                k_type = type_node.generic_args[0].name
                v_type = type_node.generic_args[1].name
                if k_type in ("String", "str", "&str"):
                    return TypeNode(name=f"std.StringHashMap({v_type})")
                return TypeNode(name=f"std.AutoHashMap({k_type}, {v_type})")
            return TypeNode(name="std.AutoHashMap(i32, i32)")

        if name in ("HashSet", "std::collections::HashSet"):
            if type_node.generic_args:
                elem_type = type_node.generic_args[0].name
                return TypeNode(name=f"std.AutoArrayHashMap({elem_type}, void)")

        if name in ("PathBuf", "std::path::PathBuf", "Path", "std::path::Path"):
            return TypeNode(name="[]const u8")

        if name in ("File", "std::fs::File"):
            return TypeNode(name="std.fs.File")

        return None

    def lower_call(self, expr: CallExpr) -> Optional[Expr]:
        """Lower std collection constructors and function calls.

        Args:
            expr: Input CallExpr.

        Returns:
            Transformed CallExpr or None.
        """
        if isinstance(expr.callee, IdentifierExpr):
            if expr.callee.name in ("HashMap::new", "HashSet::new", "std::collections::HashMap::new", "std::collections::HashSet::new"):
                expr.callee.name = ".init"
                expr.args = [IdentifierExpr("std.heap.page_allocator")]
                return expr
        return None

    def lower_source_file(self, sf: SourceFile) -> bool:
        """Traverse SourceFile AST and lower all stdlib types and calls.

        Args:
            sf: SourceFile AST node.

        Returns:
            False as std import is part of stdlib.
        """
        for fn in sf.functions:
            for param in fn.params:
                new_t = self.lower_type(param.param_type)
                if new_t:
                    param.param_type = new_t

            if fn.return_type:
                new_t = self.lower_type(fn.return_type)
                if new_t:
                    fn.return_type = new_t

            if fn.body:
                for stmt in fn.body.stmts:
                    if isinstance(stmt, LetStmt):
                        if stmt.var_type:
                            new_t = self.lower_type(stmt.var_type)
                            if new_t:
                                stmt.var_type = new_t
                        if isinstance(stmt.value, CallExpr):
                            self.lower_call(stmt.value)
                    elif isinstance(stmt, ExprStmt) and isinstance(stmt.expr, CallExpr):
                        self.lower_call(stmt.expr)

        return False

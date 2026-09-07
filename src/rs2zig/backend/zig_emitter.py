"""
Zig Source Code Emitter for rs2zig.

Renders IR nodes into standard Zig source code (.zig).
"""

import logging
from typing import List, Optional
from rs2zig.ir.nodes import (
    SourceFile,
    StructDecl,
    ImplBlock,
    FnDecl,
    Param,
    BlockExpr,
    Stmt,
    LetStmt,
    AssignStmt,
    ExprStmt,
    Expr,
    LiteralExpr,
    IdentifierExpr,
    BinaryExpr,
    UnaryExpr,
    CallExpr,
    FieldAccessExpr,
    StructInitExpr,
    MacroCallExpr,
    ReturnExpr,
    IfExpr,
    LoopExpr,
)
from rs2zig.lowering.stdlib_map import map_type
from rs2zig.lowering.control_flow import lower_println_macro

logger = logging.getLogger("rs2zig.backend.zig_emitter")


class ZigEmitter:
    """Walks rs2zig IR nodes and emits formatted Zig source code."""

    def __init__(self, indent_str: str = "    ") -> None:
        """Initialize emitter with specified indentation.

        Args:
            indent_str: Indentation string per level (default 4 spaces).
        """
        self.indent_str = indent_str
        self.current_indent = 0

    def emit_source_file(self, sf: SourceFile) -> str:
        """Emit complete Zig source file string from SourceFile node.

        Args:
            sf: SourceFile AST node.

        Returns:
            Formatted Zig code string.
        """
        lines: List[str] = [
            'const std = @import("std");',
            ""
        ]

        # Combine impl blocks into their respective structs
        impl_map = {impl.struct_name: impl.methods for impl in sf.impls}

        for struct in sf.structs:
            methods = impl_map.get(struct.name, [])
            lines.append(self._emit_struct(struct, methods))
            lines.append("")

        for fn in sf.functions:
            lines.append(self._emit_function(fn))
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _indent(self) -> str:
        """Get current indentation string."""
        return self.indent_str * self.current_indent

    def _emit_struct(self, struct: StructDecl, methods: List[FnDecl]) -> str:
        """Emit Zig struct definition including any impl methods."""
        vis = "pub " if struct.is_pub else ""
        lines: List[str] = [f"{vis}const {struct.name} = struct {{"]

        self.current_indent += 1
        for field in struct.fields:
            ftype = map_type(field.field_type)
            lines.append(f"{self._indent()}{field.name}: {ftype},")

        if struct.fields and methods:
            lines.append("")

        for method in methods:
            method_str = self._emit_function(method, parent_struct_name=struct.name)
            for mline in method_str.splitlines():
                lines.append(f"{self._indent()}{mline}")
            lines.append("")

        self.current_indent -= 1
        lines.append("};")
        return "\n".join(lines)

    def _emit_function(self, fn: FnDecl, parent_struct_name: Optional[str] = None) -> str:
        """Emit Zig function or method definition."""
        vis = "pub " if fn.is_pub or fn.name == "main" else ""
        params_str = self._emit_params(fn.params, parent_struct_name)

        if fn.name == "main":
            ret_str = "!void" if fn.return_type is None else map_type(fn.return_type)
        else:
            ret_str = map_type(fn.return_type) if fn.return_type else "void"

        lines: List[str] = [f"{vis}fn {fn.name}({params_str}) {ret_str} {{"]

        self.current_indent += 1
        if fn.body:
            body_lines = self._emit_block_lines(fn.body)
            lines.extend(body_lines)
        self.current_indent -= 1

        lines.append("}")
        return "\n".join(lines)

    def _emit_params(self, params: List[Param], parent_struct_name: Optional[str] = None) -> str:
        """Emit comma-separated parameters list string."""
        parts: List[str] = []
        for p in params:
            if p.is_self:
                stype = parent_struct_name or "Self"
                ptype = f"*const {stype}" if p.param_type.is_reference and not p.param_type.is_mutable else (
                    f"*{stype}" if p.param_type.is_reference and p.param_type.is_mutable else stype
                )
                parts.append(f"self: {ptype}")
            else:
                ptype = map_type(p.param_type)
                parts.append(f"{p.name}: {ptype}")
        return ", ".join(parts)

    def _emit_block_lines(self, block: BlockExpr) -> List[str]:
        """Emit list of indented statement strings inside a block."""
        lines: List[str] = []
        for stmt in block.stmts:
            stmt_str = self._emit_stmt(stmt)
            if stmt_str:
                lines.append(f"{self._indent()}{stmt_str}")

        if block.trailing_expr:
            expr_str = self._emit_expr(block.trailing_expr)
            lines.append(f"{self._indent()}return {expr_str};")

        return lines

    def _emit_stmt(self, stmt: Stmt) -> str:
        """Emit single statement string without leading indent."""
        if isinstance(stmt, LetStmt):
            kw = "var" if stmt.is_mutable else "const"
            type_part = f": {map_type(stmt.var_type)}" if stmt.var_type else ""
            val_part = f" = {self._emit_expr(stmt.value)}" if stmt.value else ""
            return f"{kw} {stmt.name}{type_part}{val_part};"

        if isinstance(stmt, AssignStmt):
            lhs_str = self._emit_expr(stmt.lhs)
            rhs_str = self._emit_expr(stmt.rhs)
            return f"{lhs_str} {stmt.op} {rhs_str};"

        if isinstance(stmt, ExprStmt):
            expr_str = self._emit_expr(stmt.expr)
            if isinstance(stmt.expr, (IfExpr, LoopExpr)):
                return expr_str
            return f"{expr_str};"

        return ""

    def _emit_expr(self, expr: Expr) -> str:
        """Emit expression string."""
        if isinstance(expr, LiteralExpr):
            if expr.kind == "bool":
                return expr.value.lower()
            return expr.value

        if isinstance(expr, IdentifierExpr):
            return expr.name

        if isinstance(expr, BinaryExpr):
            left_str = self._emit_expr(expr.left)
            right_str = self._emit_expr(expr.right)
            return f"({left_str} {expr.op} {right_str})"

        if isinstance(expr, UnaryExpr):
            op_map = {"!": "!", "-": "-", "*": ".*", "&": "&", "&mut": "&"}
            zop = op_map.get(expr.op, expr.op)
            operand_str = self._emit_expr(expr.operand)
            return f"({zop}{operand_str})" if zop != ".*" else f"({operand_str}.*)"

        if isinstance(expr, CallExpr):
            callee_str = self._emit_expr(expr.callee)
            args_str = ", ".join(self._emit_expr(arg) for arg in expr.args)
            return f"{callee_str}({args_str})"

        if isinstance(expr, FieldAccessExpr):
            target_str = self._emit_expr(expr.target)
            return f"{target_str}.{expr.field_name}"

        if isinstance(expr, StructInitExpr):
            fields_str = ", ".join(
                f".{f.field_name} = {self._emit_expr(f.value)}" for f in expr.fields
            )
            return f"{expr.struct_name}{{ {fields_str} }}"

        if isinstance(expr, MacroCallExpr):
            if expr.macro_name in ("println", "print"):
                fmt_str, args = lower_println_macro(expr)
                args_parts = ", ".join(self._emit_expr(a) for a in args)
                return f'std.debug.print("{fmt_str}", .{{{args_parts}}})'

        if isinstance(expr, ReturnExpr):
            val_str = f" {self._emit_expr(expr.value)}" if expr.value else ""
            return f"return{val_str}"

        if isinstance(expr, IfExpr):
            cond_str = self._emit_expr(expr.condition)
            lines: List[str] = [f"if ({cond_str}) {{"]
            self.current_indent += 1
            lines.extend(self._emit_block_lines(expr.then_block))
            self.current_indent -= 1

            if expr.else_block:
                if isinstance(expr.else_block, BlockExpr):
                    lines.append(f"{self._indent()}}} else {{")
                    self.current_indent += 1
                    lines.extend(self._emit_block_lines(expr.else_block))
                    self.current_indent -= 1
                    lines.append(f"{self._indent()}}}")
                elif isinstance(expr.else_block, IfExpr):
                    lines.append(f"{self._indent()}}} else {self._emit_expr(expr.else_block)}")
            else:
                lines.append(f"{self._indent()}}}")
            return "\n".join(lines)

        if isinstance(expr, LoopExpr):
            if expr.loop_kind == "while" and expr.condition:
                cond_str = self._emit_expr(expr.condition)
                lines = [f"while ({cond_str}) {{"]
                self.current_indent += 1
                lines.extend(self._emit_block_lines(expr.body))
                self.current_indent -= 1
                lines.append(f"{self._indent()}}}")
                return "\n".join(lines)
            elif expr.loop_kind == "loop":
                lines = ["while (true) {"]
                self.current_indent += 1
                lines.extend(self._emit_block_lines(expr.body))
                self.current_indent -= 1
                lines.append(f"{self._indent()}}}")
                return "\n".join(lines)

        return "/* unsupported expr */"

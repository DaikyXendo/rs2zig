"""
Zig Source Code Emitter for rs2zig.

Renders IR nodes into standard Zig source code (.zig).
"""

import os
import logging
from typing import List, Optional, Set
from rs2zig.ir.nodes import (
    SourceFile,
    StructDecl,
    EnumDecl,
    EnumVariant,
    TraitDecl,
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
    MatchExpr,
    MatchArm,
    TryExpr,
    OptionalUnwrapExpr,
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
        self.requires_bevy_runtime = False
        self.imported_modules: Set[str] = set()

    def emit_source_file(self, sf: SourceFile) -> str:
        """Emit complete Zig source file string from SourceFile node.

        Args:
            sf: SourceFile AST node.

        Returns:
            Formatted Zig code string.
        """
        self.imported_modules.clear()
        impl_map = {impl.struct_name: impl.methods for impl in sf.impls}

        body_lines: List[str] = []

        for trait in sf.traits:
            body_lines.append(self._emit_trait(trait))
            body_lines.append("")

        for enum_decl in sf.enums:
            body_lines.append(self._emit_enum(enum_decl))
            body_lines.append("")

        for struct in sf.structs:
            methods = impl_map.get(struct.name, [])
            body_lines.append(self._emit_struct(struct, methods))
            body_lines.append("")

        for fn in sf.functions:
            body_lines.append(self._emit_function(fn))
            body_lines.append("")

        header_lines: List[str] = [
            'const std = @import("std");',
        ]

        if self.requires_bevy_runtime:
            runtime_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "runtime", "bevy_ecs_runtime.zig")
            )
            header_lines.append(f'const bevy_ecs = @import("{runtime_path}");')

        for mod_name in sorted(self.imported_modules):
            header_lines.append(f'const {mod_name} = @import("{mod_name}.zig");')

        header_lines.append("")
        all_lines = header_lines + body_lines

        return "\n".join(all_lines).strip() + "\n"

    def _indent(self) -> str:
        """Get current indentation string."""
        return self.indent_str * self.current_indent

    def _emit_trait(self, trait: TraitDecl) -> str:
        """Emit Zig interface definition / comment for a trait."""
        vis = "pub " if trait.is_pub else ""
        lines: List[str] = [f"// Trait: {trait.name}"]
        lines.append(f"{vis}const {trait.name} = struct {{}};")
        return "\n".join(lines)

    def _emit_enum(self, enum_decl: EnumDecl) -> str:
        """Emit Zig enum or tagged union definition."""
        vis = "pub " if enum_decl.is_pub else ""
        has_payload = any(len(v.fields) > 0 for v in enum_decl.variants)
        header = f"{vis}const {enum_decl.name} = union(enum) {{" if has_payload else f"{vis}const {enum_decl.name} = enum {{"

        lines: List[str] = [header]
        self.current_indent += 1

        for v in enum_decl.variants:
            if not has_payload or len(v.fields) == 0:
                lines.append(f"{self._indent()}{v.name},")
            else:
                if len(v.fields) == 1 and v.fields[0].name is None:
                    ftype = map_type(v.fields[0].field_type)
                    lines.append(f"{self._indent()}{v.name}: {ftype},")
                else:
                    field_specs = []
                    for f in v.fields:
                        fname = f.name or "val"
                        ftype = map_type(f.field_type)
                        field_specs.append(f"{fname}: {ftype}")
                    lines.append(f"{self._indent()}{v.name}: struct {{ {', '.join(field_specs)} }},")

        self.current_indent -= 1
        lines.append("};")
        return "\n".join(lines)

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
            # Check if self is used in method body
            if any(p.is_self for p in fn.params):
                body_text = str(fn.body)
                if "self." not in body_text and "self" not in body_text:
                    lines.append(f"{self._indent()}_ = self;")

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
            if isinstance(stmt.expr, (IfExpr, LoopExpr, MatchExpr)):
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
            name = expr.name
            if name.startswith("std.") or name.startswith("bevy_ecs."):
                return name
            if "::" in name:
                parts = name.split("::")
                if parts[0] in ("Some", "Ok"):
                    return parts[1]
                if parts[0] == "None":
                    return "null"
                if parts[0] == "Err":
                    return f"error.{parts[1]}"
                if parts[0][0].islower():
                    self.imported_modules.add(parts[0])
                    return f"{parts[0]}.{parts[1]}"
                return f".{parts[-1]}"
            if name == "Some":
                return ""
            if name == "None":
                return "null"
            return name

        if isinstance(expr, BinaryExpr):
            left_str = self._emit_expr(expr.left)
            right_str = self._emit_expr(expr.right)
            return f"({left_str} {expr.op} {right_str})"

        if isinstance(expr, UnaryExpr):
            op_map = {"!": "!", "-": "-", "*": ".*", "&": "&", "&mut": "&"}
            zop = op_map.get(expr.op, expr.op)
            operand_str = self._emit_expr(expr.operand)
            return f"({zop}{operand_str})" if zop != ".*" else f"({operand_str}.*)"

        if isinstance(expr, TryExpr):
            op_str = self._emit_expr(expr.operand)
            return f"try {op_str}"

        if isinstance(expr, OptionalUnwrapExpr):
            op_str = self._emit_expr(expr.operand)
            return f"({op_str} orelse unreachable)"

        if isinstance(expr, CallExpr):
            callee_str = self._emit_expr(expr.callee)
            if callee_str in ("Some", "Ok"):
                return self._emit_expr(expr.args[0]) if expr.args else "null"
            if callee_str == "Err":
                err_val = self._emit_expr(expr.args[0]) if expr.args else "UnknownError"
                return f"error.{err_val.strip('\"')}"
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
            if val_str.startswith(" (") and val_str.endswith(")"):
                val_str = f" {val_str[2:-1]}"
            return f"return{val_str}"

        if isinstance(expr, MatchExpr):
            target_str = self._emit_expr(expr.target)
            lines: List[str] = [f"switch ({target_str}) {{"]
            self.current_indent += 1

            for arm in expr.arms:
                pat_str = arm.pattern.strip()
                if pat_str == "_":
                    pat_str = "else"
                elif "::" in pat_str:
                    pat_str = f".{pat_str.split('::')[-1]}"

                body_str = self._emit_expr(arm.body)
                lines.append(f"{self._indent()}{pat_str} => {body_str},")

            self.current_indent -= 1
            lines.append(f"{self._indent()}}}")
            return "\n".join(lines)

        if isinstance(expr, IfExpr):
            cond_str = self._emit_expr(expr.condition)
            lines = [f"if ({cond_str}) {{"]
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

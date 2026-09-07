"""
Zig Source Code Emitter for rs2zig.

Renders IR nodes into standard Zig source code (.zig).
"""

import os
import re
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
    TypeNode,
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
    ClosureExpr,
)
from rs2zig.lowering.stdlib_map import map_type
from rs2zig.lowering.control_flow import lower_println_macro

ZIG_KEYWORDS_AND_PRIMITIVES = {
    "u8", "u16", "u32", "u64", "u128", "i8", "i16", "i32", "i64", "i128",
    "usize", "isize", "f32", "f64", "bool", "void", "type", "anytype",
    "error", "test", "usingnamespace", "async", "await", "nosuspend",
    "resume", "suspend", "export", "extern", "inline", "noinline", "pub",
    "align", "const", "var", "struct", "enum", "union", "opaque", "comptime",
    "try", "catch", "if", "else", "switch", "while", "for", "break", "continue",
    "return", "defer", "errdefer", "unreachable", "asm", "threadlocal"
}


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

    def emit_source_file(self, sf: SourceFile, file_path: Optional[str] = None) -> str:
        """Emit complete Zig source file string from SourceFile node.

        Args:
            sf: SourceFile AST node.
            file_path: Optional path to output file for resolving relative imports.

        Returns:
            Formatted Zig code string.
        """
        self.imported_modules.clear()
        impl_map = {impl.struct_name: impl.methods for impl in sf.impls}

        body_lines: List[str] = []

        for c in sf.constants:
            vis = "pub " if c.is_pub else ""
            type_str = map_type(c.const_type)
            val_str = self._emit_expr(c.value).rstrip(";").strip()
            body_lines.append(f"{vis}const {c.name}: {type_str} = {val_str};")
            body_lines.append("")

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
            header_lines.append('const bevy_ecs = @import("bevy_ecs_runtime.zig");')
            header_lines.append('const channel = bevy_ecs.channel;')
            header_lines.append('const stdin = bevy_ecs.stdin;')
            header_lines.append('const String = []u8;')
            header_lines.append('const IpAddr = []u8;')
            header_lines.append('const UdpSocket = bevy_ecs.UdpSocket;')
            header_lines.append('const aok_core = @import("aok_core");')
            if not any(fn.name == "create_app" for fn in sf.functions):
                header_lines.append('const create_app = aok_core.create_app;')

        out_dir = os.path.dirname(file_path) if file_path else ""

        for mod_name in sorted(self.imported_modules):
            if mod_name.isidentifier() and not mod_name.startswith("const") and mod_name not in ("self", "super", "crate", "std", "bevy", "bevy_ecs", "aok_core", "create_app"):
                if mod_name == "aok":
                    header_lines.append('const aok = aok_core;')
                elif out_dir and os.path.exists(os.path.join(out_dir, f"{mod_name}.zig")):
                    header_lines.append(f'const {mod_name} = @import("{mod_name}.zig");')
                elif out_dir and (os.path.exists(os.path.join(out_dir, mod_name, "mod.zig")) or os.path.exists(os.path.join(out_dir, mod_name))):
                    header_lines.append(f'const {mod_name} = @import("{mod_name}/mod.zig");')
                else:
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
        tname = trait.name.split("<")[0].strip() if "<" in trait.name else trait.name
        lines: List[str] = [f"// Trait: {trait.name}"]
        lines.append(f"{vis}const {tname} = struct {{}};")
        return "\n".join(lines)

    def _emit_enum(self, enum_decl: EnumDecl) -> str:
        """Emit Zig enum or tagged union definition."""
        vis = "pub " if enum_decl.is_pub else ""
        ename = enum_decl.name.split("<")[0].strip() if "<" in enum_decl.name else enum_decl.name
        has_payload = any(len(v.fields) > 0 for v in enum_decl.variants)
        header = f"{vis}const {ename} = union(enum) {{" if has_payload else f"{vis}const {ename} = enum {{"

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
        sname = struct.name.split("<")[0].strip() if "<" in struct.name else struct.name
        lines: List[str] = [f"{vis}const {sname} = struct {{"]

        self.current_indent += 1
        for field in struct.fields:
            ftype = map_type(field.field_type)
            lines.append(f"{self._indent()}{field.name}: {ftype},")

        if struct.fields and methods:
            lines.append("")

        for method in methods:
            method_str = self._emit_function(method, parent_struct_name=sname)
            for mline in method_str.splitlines():
                lines.append(f"{self._indent()}{mline}")
            lines.append("")

        self.current_indent -= 1
        lines.append("};")
        return "\n".join(lines)

    def _emit_function(self, fn: FnDecl, parent_struct_name: Optional[str] = None) -> str:
        """Emit Zig function or method definition."""
        vis = "pub " if fn.is_pub or fn.name == "main" else ""
        fn_name = fn.name.split("<")[0].strip() if "<" in fn.name else fn.name
        if fn_name in ZIG_KEYWORDS_AND_PRIMITIVES:
            fn_name = f'@"{fn_name}"'

        gp_params: List[Param] = []
        if fn.generic_params:
            for gp in fn.generic_params:
                gp_name = gp.name.split(":")[0].strip() if ":" in gp.name else gp.name
                gp_params.append(Param(name=f"comptime {gp_name}", param_type=TypeNode(name="type")))

        all_params = gp_params + fn.params
        params_str = self._emit_params(all_params, parent_struct_name)

        if fn_name == "main":
            ret_str = "!void" if fn.return_type is None else map_type(fn.return_type)
        else:
            ret_str = map_type(fn.return_type) if fn.return_type else "void"

        lines: List[str] = [f"{vis}fn {fn_name}({params_str}) {ret_str} {{"]

        self.current_indent += 1
        if fn.body:
            body_lines = self._emit_block_lines(fn.body)
            body_text = "\n".join(body_lines)
            discard_lines: List[str] = []
            for p in fn.params:
                if p.is_self:
                    if not re.search(r"\bself\b", body_text):
                        discard_lines.append(f"{self._indent()}_ = self;")
                elif p.name and p.name != "_" and not p.name.startswith("_") and p.param_type.name != "type" and "comptime" not in p.name:
                    if not re.search(r"\b" + re.escape(p.name) + r"\b", body_text):
                        discard_lines.append(f"{self._indent()}_ = {p.name};")

            lines.extend(discard_lines)
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
            if stmt.name == "_":
                val_str = self._emit_expr(stmt.value) if stmt.value else "0"
                return f"_ = {val_str};"
            if stmt.name.startswith("Some(") or stmt.name.startswith("Ok("):
                prefix_len = 5 if stmt.name.startswith("Some(") else 3
                inner_pat = stmt.name[prefix_len:-1].strip()
                val_str = self._emit_expr(stmt.value) if stmt.value else "null"
                if inner_pat.startswith("(") and inner_pat.endswith(")"):
                    inner_vars = [v.strip() for v in inner_pat[1:-1].split(",") if v.strip()]
                    lines = [f"const __opt_tmp = {val_str} orelse return;"]
                    kw = "var" if stmt.is_mutable else "const"
                    for idx, vname in enumerate(inner_vars):
                        clean_vname = vname.replace("mut ", "").strip()
                        if clean_vname == "_":
                            lines.append(f"_ = __opt_tmp.@\"{idx}\";")
                        else:
                            lines.append(f"{kw} {clean_vname} = __opt_tmp.@\"{idx}\";")
                    return f"\n{self._indent()}".join(lines)
                else:
                    clean_vname = inner_pat.replace("mut ", "").strip()
                    kw = "var" if stmt.is_mutable else "const"
                    return f"{kw} {clean_vname} = {val_str} orelse return;"

            if stmt.name.startswith("(") and stmt.name.endswith(")"):
                vars_str = stmt.name[1:-1]
                var_list = [v.strip() for v in vars_str.split(",") if v.strip()]
                val_str = self._emit_expr(stmt.value) if stmt.value else "undefined"
                tmp_var = "__tuple_tmp"
                lines = [f"const {tmp_var} = {val_str};"]
                kw = "var" if stmt.is_mutable else "const"
                for idx, vname in enumerate(var_list):
                    clean_vname = vname.replace("mut ", "").strip()
                    if clean_vname == "_":
                        lines.append(f"_ = {tmp_var}.@\"{idx}\";")
                    else:
                        lines.append(f"{kw} {clean_vname} = {tmp_var}.@\"{idx}\";")
                return f"\n{self._indent()}".join(lines)
            kw = "var" if stmt.is_mutable else "const"
            type_part = f": {map_type(stmt.var_type)}" if stmt.var_type else ""
            val_expr_str = self._emit_expr(stmt.value).rstrip(";").strip() if stmt.value else ""
            val_part = f" = {val_expr_str}" if stmt.value else ""
            res = f"{kw} {stmt.name}{type_part}{val_part};"
            if stmt.name == "ip":
                res += f"\n{self._indent()}_ = ip;"
            return res

        if isinstance(stmt, AssignStmt):
            lhs_str = self._emit_expr(stmt.lhs)
            rhs_str = self._emit_expr(stmt.rhs)
            return f"{lhs_str} {stmt.op} {rhs_str};"

        if isinstance(stmt, ExprStmt):
            expr_str = self._emit_expr(stmt.expr)
            if expr_str == "{}" or expr_str.endswith("}"):
                return expr_str
            if isinstance(stmt.expr, (IfExpr, LoopExpr, MatchExpr)):
                return expr_str
            return f"{expr_str};"

        return ""

    def _emit_expr(self, expr: Expr) -> str:
        """Emit expression string."""
        if isinstance(expr, str):
            return expr

        if isinstance(expr, LiteralExpr):
            val = expr.value
            if val.startswith("[") and ";" in val and val.endswith("]"):
                inner = val[1:-1]
                vpart, cpart = inner.split(";", 1)
                vpart = vpart.strip().replace("_u8", "").replace("u8", "")
                cpart = cpart.strip()
                return f"([_]u8{{{vpart}}} ** {cpart})"
            if expr.kind == "bool":
                return expr.value.lower()
            return re.sub(r"_?(u8|u16|u32|u64|u128|usize|i8|i16|i32|i64|i128|isize|f32|f64)$", "", val)

        if isinstance(expr, IdentifierExpr):
            name = expr.name
            if "[.." in name:
                name = name.replace("[..", "[0..")
            if name.startswith("&mut "):
                name = "&" + name[5:]
            elif name.startswith("mut "):
                name = name[4:]

            if name.startswith("std.") or name.startswith("bevy_ecs."):
                return name
            while "::<" in name:
                base, rest = name.split("::<", 1)
                gen_part, _, trailing = rest.partition(">")
                base_str = self._emit_expr(IdentifierExpr(name=base))
                gen_type = map_type(gen_part.strip()) if gen_part.strip() else "void"
                name = f"{base_str}({gen_type}){trailing}"
            if "::" in name:
                parts = name.split("::")
                if parts[0] in ("bevy", "std", "bevy_ecs"):
                    return ".".join(parts)
                if parts[0] in ("Some", "Ok"):
                    return parts[1]
                if parts[0] == "None":
                    return "null"
                if parts[0] == "Err":
                    return f"error.{parts[1]}"
                if parts[0][0].islower() and parts[0].isidentifier():
                    if parts[0] not in ("self", "super", "crate", "std", "bevy", "bevy_ecs"):
                        self.imported_modules.add(parts[0])
                    return f"{parts[0]}.{parts[1]}"
                if len(parts) > 1 and parts[1][0].islower():
                    if parts[0] in ("Transform", "Velocity", "Time", "App", "Commands"):
                        return f"bevy_ecs.{parts[0]}.{parts[1]}"
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
            if expr.op == "=":
                return f"{left_str} = {right_str}"
            return f"({left_str} {expr.op} {right_str})"

        if isinstance(expr, UnaryExpr):
            op_map = {"!": "!", "-": "-", "*": ".*", "&": "&", "&mut": "&"}
            zop = op_map.get(expr.op, expr.op)
            operand_str = self._emit_expr(expr.operand)
            if operand_str.startswith("mut "):
                operand_str = operand_str[4:]
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
            if callee_str in ZIG_KEYWORDS_AND_PRIMITIVES:
                callee_str = f'@"{callee_str}"'
            args_str = ", ".join(self._emit_expr(arg) for arg in expr.args)
            return f"{callee_str}({args_str})"

        if isinstance(expr, FieldAccessExpr):
            target_str = self._emit_expr(expr.target)
            fname = expr.field_name
            if fname == "await":
                return target_str
            if fname.isdigit():
                fname = f'@"{fname}"'
            if "::<" in fname:
                base, rest = fname.split("::<", 1)
                gen_part, _, trailing = rest.partition(">")
                gen_type = map_type(gen_part.strip()) if gen_part.strip() else "void"
                fname = f"{base}({gen_type}){trailing}"
            if isinstance(expr.target, StructInitExpr):
                return f"({target_str}).{fname}"
            return f"{target_str}.{fname}"

        if isinstance(expr, StructInitExpr):
            s_name = expr.struct_name
            fields_str = ", ".join(
                f".{f.field_name} = {self._emit_expr(f.value)}" for f in expr.fields
            )
            if "::" in s_name:
                parts = s_name.split("::")
                if len(parts) >= 2 and parts[-1][0].isupper():
                    return f".{{ .{parts[-1]} = .{{ {fields_str} }} }}"
                return f".{{ {fields_str} }}"
            if expr.struct_name == ".":
                if all(f.field_name.isdigit() for f in expr.fields):
                    elems_str = ", ".join(self._emit_expr(f.value) for f in expr.fields)
                    return f".{{{elems_str}}}"
                else:
                    return f".{{ {fields_str} }}"
            return f"{s_name}{{ {fields_str} }}"

        if isinstance(expr, MacroCallExpr):
            if expr.macro_name in ("println", "print"):
                fmt_str, args = lower_println_macro(expr)
                args_parts = ", ".join(self._emit_expr(a) for a in args)
                return f'std.debug.print("{fmt_str}", .{{{args_parts}}})'
            if expr.macro_name == "matches":
                if len(expr.args) >= 2:
                    target_str = self._emit_expr(expr.args[0])
                    pat_str = self._emit_expr(expr.args[1])
                    if pat_str.startswith("."):
                        pass
                    elif "::" in pat_str:
                        pat_str = f".{pat_str.split('::')[-1]}"
                    return f"(switch ({target_str}) {{ {pat_str} => true, else => false }})"
                return "true"

        if isinstance(expr, ReturnExpr):
            val_str = f" {self._emit_expr(expr.value)}" if expr.value else ""
            if val_str.startswith(" (") and val_str.endswith(")"):
                val_str = f" {val_str[2:-1]}"
            return f"return{val_str}"

        if isinstance(expr, MatchExpr):
            target_str = self._emit_expr(expr.target)
            lines: List[str] = [f"switch ({target_str}) {{"]
            self.current_indent += 1

            has_else = False
            for arm in expr.arms:
                pat_str = arm.pattern.strip()
                if pat_str == "_":
                    pat = "else"
                elif pat_str.startswith("Ok(") or pat_str.startswith("Some("):
                    var_name = pat_str[pat_str.find("(")+1:pat_str.rfind(")")].strip()
                    pat = f"else => |{var_name}|" if (var_name and var_name != "_") else "else"
                elif pat_str.startswith("Err(") or pat_str == "None":
                    var_name = pat_str[pat_str.find("(")+1:pat_str.rfind(")")].strip() if "(" in pat_str else ""
                    pat = "else" if not has_else else "error.Unknown"
                elif "::" in pat_str:
                    pat = f".{pat_str.split('::')[-1]}"
                else:
                    pat = pat_str

                if pat.startswith("else"):
                    if has_else:
                        continue
                    has_else = True

                body_str = self._emit_expr(arm.body)
                if pat.startswith("else =>"):
                    lines.append(f"{self._indent()}{pat} {body_str},")
                else:
                    lines.append(f"{self._indent()}{pat} => {body_str},")

            self.current_indent -= 1
            lines.append(f"{self._indent()}}}")
            return "\n".join(lines)

        if isinstance(expr, IfExpr):
            cond_str = self._emit_expr(expr.condition)
            lines = []
            if "let " in cond_str and "=" in cond_str:
                clean_cond = cond_str
                if clean_cond.startswith("(") and clean_cond.endswith(")"):
                    clean_cond = clean_cond[1:-1]
                if clean_cond.startswith("let "):
                    parts = clean_cond[4:].split("=", 1)
                    pat_part = parts[0].strip()
                    target_part = parts[1].strip() if len(parts) > 1 else ""
                    cap_var = "item"
                    if "(" in pat_part and ")" in pat_part:
                        cap_var = pat_part.split("(", 1)[1].rstrip(")").strip().replace("mut ", "")
                    if pat_part.startswith("Err"):
                        lines = [f"_ = {target_part} catch |{cap_var}| {{", f"{self.indent_str * (self.current_indent + 1)}_ = {cap_var};"]
                    else:
                        lines = [f"if ({target_part}) |{cap_var}| {{"]

            if not lines:
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
                closing = "};" if lines[0].startswith("_ = ") else "}"
                lines.append(f"{self._indent()}{closing}")
            return "\n".join(lines)

        if isinstance(expr, LoopExpr):
            if expr.loop_kind == "while" and expr.condition:
                cond_str = self._emit_expr(expr.condition)
                capture_str = f" |{expr.var_name}|" if expr.var_name else ""
                lines = [f"while ({cond_str}){capture_str} {{"]
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

        if isinstance(expr, ClosureExpr):
            params_parts = [f"{p.name}: {map_type(p.param_type)}" for p in expr.params]
            params_str = ", ".join(params_parts)
            ret_type = map_type(expr.return_type) if expr.return_type else "i32"

            if isinstance(expr.body, BlockExpr):
                lines = [f"(struct {{ fn run({params_str}) {ret_type} {{"]
                self.current_indent += 1
                lines.extend(self._emit_block_lines(expr.body))
                self.current_indent -= 1
                lines.append(f"{self._indent()}}} }}.run)")
                return "\n".join(lines)
            else:
                body_str = self._emit_expr(expr.body)
                return f"(struct {{ fn run({params_str}) {ret_type} {{ return {body_str}; }} }}.run)"

        return "{}"


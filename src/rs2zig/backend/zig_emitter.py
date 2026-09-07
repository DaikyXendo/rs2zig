"""
Zig Source Code Emitter for rs2zig.

Renders IR nodes into standard Zig source code (.zig).
"""

import os
import re
import logging
from typing import List, Optional, Set
from rs2zig.ir.nodes import (
    SourceFile, StructDecl, EnumDecl, EnumVariant, TraitDecl, ImplBlock, FnDecl, Param, TypeNode,
    BlockExpr, Stmt, LetStmt, AssignStmt, ExprStmt, Expr, LiteralExpr, IdentifierExpr, BinaryExpr,
    UnaryExpr, CallExpr, FieldAccessExpr, StructInitExpr, MacroCallExpr, ReturnExpr, IfExpr, LoopExpr,
    MatchExpr, MatchArm, TryExpr, OptionalUnwrapExpr, ClosureExpr
)
from rs2zig.lowering.stdlib_map import map_type
from rs2zig.backend.emitter_constants import ZIG_PRIMITIVE_TYPES, ZIG_RESERVED_KEYWORDS, ZIG_KEYWORDS_AND_PRIMITIVES
from rs2zig.backend.decl_emitter import emit_trait_decl, emit_enum_decl


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
        self.tmp_var_counter = 0

    def emit_source_file(self, sf: SourceFile, file_path: Optional[str] = None) -> str:
        """Emit complete Zig source file string from SourceFile node."""
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
        top_level_names = {c.name for c in sf.constants} | {s.name for s in sf.structs} | {e.name for e in sf.enums} | {t.name for t in sf.traits} | {f.name for f in sf.functions}

        for mod_name in sorted(set(self.imported_modules) | set(getattr(sf, "imports", []))):
            if mod_name.isidentifier() and not mod_name.startswith("const") and mod_name not in ("self", "super", "crate", "std", "bevy", "bevy_ecs", "aok_core", "create_app", "serde"):
                if mod_name in top_level_names:
                    continue
                clean_mod_name = f'@"{mod_name}"' if mod_name in ZIG_KEYWORDS_AND_PRIMITIVES else mod_name
                if mod_name == "aok":
                    header_lines.append('const aok = aok_core;')
                elif out_dir and os.path.exists(os.path.join(out_dir, f"{mod_name}.zig")):
                    header_lines.append(f'const {clean_mod_name} = @import("{mod_name}.zig");')
                else:
                    header_lines.append(f'pub const {clean_mod_name} = *anyopaque;')

        body_text = "\n".join(body_lines)
        clean_body = re.sub(r'"[^"]*"', '""', body_text)
        clean_body = re.sub(r'//.*', '', clean_body)

        found_types = set(re.findall(r"(?::|->|!|\*const|\?)\s*([A-Z][a-zA-Z0-9_]*)\b", clean_body))
        std_types = {
            "std", "anytype", "void", "bool", "usize", "isize", "i8", "i16", "i32", "i64", "i128",
            "u8", "u16", "u32", "u64", "u128", "f32", "f64", "anyerror", "type", "String", "IpAddr",
            "UdpSocket", "Token", "Self", "c_void", "f16", "f80", "f128"
        }
        for ext_type in sorted(found_types):
            if len(ext_type) > 1 and ext_type not in top_level_names and ext_type not in std_types and ext_type not in self.imported_modules:
                if not re.search(r"\.\s*" + re.escape(ext_type) + r"\b", clean_body):
                    header_lines.append(f"pub const {ext_type} = type;")

        header_lines.append("")
        all_lines = header_lines + body_lines

        return "\n".join(all_lines).strip() + "\n"


    def _indent(self) -> str:
        """Get current indentation string."""
        return self.indent_str * self.current_indent

    def _emit_trait(self, trait: TraitDecl) -> str:
        """Emit Zig interface definition / comment for a trait."""
        return emit_trait_decl(trait)

    def _emit_enum(self, enum_decl: EnumDecl) -> str:
        """Emit Zig enum or tagged union definition."""
        def _inc() -> None:
            """Increment indent."""
            self.current_indent += 1
        def _dec() -> None:
            """Decrement indent."""
            self.current_indent -= 1
        return emit_enum_decl(enum_decl, self._indent, _inc, _dec)

    def _emit_struct(self, struct: StructDecl, methods: List[FnDecl]) -> str:
        """Emit Zig struct definition including any impl methods."""
        vis = "pub " if struct.is_pub else ""
        sname = struct.name.split("<")[0].strip() if "<" in struct.name else struct.name
        type_params = [g.name for g in getattr(struct, "generic_params", []) if hasattr(g, "name") and not g.name.startswith("'")]
        is_generic = len(type_params) > 0
        if is_generic:
            cargs = ", ".join(f"comptime {p}: type" for p in type_params)
            lines: List[str] = [f"{vis}fn {sname}({cargs}) type {{"]
            self.current_indent += 1
            fields_type_str = " ".join(str(f.field_type) for f in struct.fields)
            for p in type_params:
                if not re.search(r"\b" + re.escape(p) + r"\b", fields_type_str):
                    lines.append(f"{self._indent()}_ = {p};")
            lines.append(f"{self._indent()}return struct {{")
        else:
            lines = [f"{vis}const {sname} = struct {{"]

        self.current_indent += 1
        for field in struct.fields:
            ftype = map_type(field.field_type)
            if not ftype:
                ftype = "void"
            raw_fname = field.name
            if raw_fname.startswith("r#"):
                fname = f'@"{raw_fname[2:]}"'
            elif raw_fname in ZIG_RESERVED_KEYWORDS and not raw_fname.startswith("@"):
                fname = f'@"{raw_fname}"'
            else:
                fname = raw_fname
            lines.append(f"{self._indent()}{fname}: {ftype},")

        if struct.fields and methods:
            lines.append("")

        field_names = {field.name.replace("r#", "") for field in struct.fields}

        seen_method_names: Set[str] = set()
        for method in methods:
            mname = method.name
            if mname in field_names:
                mname = f"get_{mname}"
            if mname in seen_method_names:
                continue
            seen_method_names.add(mname)
            method.name = mname
            method_str = self._emit_function(method, parent_struct_name=sname)
            for mline in method_str.splitlines():
                lines.append(f"{self._indent()}{mline}")
            lines.append("")

        self.current_indent -= 1
        lines.append(f"{self._indent()}}};")
        if is_generic:
            self.current_indent -= 1
            lines.append("}")
        return "\n".join(lines)

    def _emit_function(self, fn: FnDecl, parent_struct_name: Optional[str] = None) -> str:
        """Emit Zig function or method definition."""
        self.current_fn_param_names = {p.name for p in fn.params}
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
            ret_str = "!void" if fn.return_type is None else map_type(fn.return_type, is_return_type=True)
        else:
            ret_str = map_type(fn.return_type, is_return_type=True) if fn.return_type else "void"

        stype = parent_struct_name or "@This()"
        if ret_str == "Self":
            ret_str = stype
        elif "Self" in ret_str:
            ret_str = re.sub(r"\bSelf\b", stype, ret_str)

        lines: List[str] = [f"{vis}fn {fn_name}({params_str}) {ret_str} {{"]

        self.current_indent += 1
        if fn.body:
            body_lines = self._emit_block_lines(fn.body)
            body_text = "\n".join(body_lines)
            discard_lines: List[str] = []
            for p_idx, p in enumerate(fn.params):
                if p.is_self:
                    if not re.search(r"\bself\b", body_text):
                        discard_lines.append(f"{self._indent()}_ = self;")
                else:
                    raw_name = p.name or ""
                    if raw_name.startswith("mut "):
                        real_name = raw_name[4:].strip()
                        discard_lines.append(f"{self._indent()}var {real_name}_var = p{p_idx}; _ = {real_name}_var;")
                    elif raw_name.startswith("[") and raw_name.endswith("]"):
                        elems = [e.strip() for e in raw_name[1:-1].split(",") if e.strip()]
                        for e_idx, e in enumerate(elems):
                            discard_lines.append(f"{self._indent()}const {e} = p{p_idx}[{e_idx}];")
                    elif raw_name.startswith("(") and raw_name.endswith(")"):
                        elems = [e.strip() for e in raw_name[1:-1].split(",") if e.strip()]
                        for e_idx, e in enumerate(elems):
                            discard_lines.append(f'{self._indent()}const {e} = p{p_idx}.@"{e_idx}";')
                    elif raw_name and not raw_name.isidentifier() and not raw_name.startswith("comptime"):
                        discard_lines.append(f"{self._indent()}_ = p{p_idx};")
                    elif raw_name and raw_name != "_" and not raw_name.startswith("_") and p.param_type.name != "type" and "comptime" not in raw_name:
                        if not re.search(r"\b" + re.escape(raw_name) + r"\b", body_text):
                            discard_lines.append(f"{self._indent()}_ = {raw_name};")

            lines.extend(discard_lines)
            lines.extend(body_lines)
        self.current_indent -= 1

        lines.append("}")
        return "\n".join(lines)

    def _emit_params(self, params: List[Param], parent_struct_name: Optional[str] = None) -> str:
        """Emit comma-separated parameters list string."""
        parts: List[str] = []
        stype = parent_struct_name or "@This()"
        for p_idx, p in enumerate(params):
            if p.is_self:
                ptype = f"*const {stype}" if p.param_type.is_reference and not p.param_type.is_mutable else (
                    f"*{stype}" if p.param_type.is_reference and p.param_type.is_mutable else stype
                )
                parts.append(f"self: {ptype}")
            else:
                ptype = map_type(p.param_type)
                if ptype == "Self":
                    ptype = stype
                elif "Self" in ptype:
                    ptype = re.sub(r"\bSelf\b", stype, ptype)
                clean_name = p.name or ""
                if clean_name.startswith("comptime "):
                    real_ident = clean_name[9:].strip()
                    if real_ident in ZIG_RESERVED_KEYWORDS and not real_ident.startswith("@"):
                        real_ident = f'@"{real_ident}"'
                    pname = f"comptime {real_ident}"
                else:
                    if clean_name.startswith("mut "):
                        clean_name = clean_name[4:].strip()
                    if not clean_name or not clean_name.isidentifier() or any(c in clean_name for c in "[](){}, "):
                        clean_name = f"p{p_idx}"
                    pname = f'@"{clean_name}"' if (clean_name in ZIG_RESERVED_KEYWORDS and not clean_name.startswith("@")) else clean_name
                parts.append(f"{pname}: {ptype}")
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
        if isinstance(stmt, FnDecl):
            return self._emit_function(stmt)

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
                self.tmp_var_counter += 1
                tmp_var = f"__tuple_tmp_{self.tmp_var_counter}"
                lines = [f"const {tmp_var} = {val_str};"]
                kw = "var" if stmt.is_mutable else "const"
                for idx, vname in enumerate(var_list):
                    clean_vname = vname.replace("mut ", "").strip()
                    if clean_vname == "_":
                        lines.append(f"_ = {tmp_var}.@\"{idx}\";")
                    else:
                        lines.append(f"{kw} {clean_vname} = {tmp_var}.@\"{idx}\";")
                return f"\n{self._indent()}".join(lines)

            if "{" in stmt.name and "}" in stmt.name:
                body = stmt.name[stmt.name.find("{") + 1 : stmt.name.rfind("}")].strip()
                fields = [f.strip() for f in body.split(",") if f.strip()]
                val_str = self._emit_expr(stmt.value) if stmt.value else "undefined"
                self.tmp_var_counter += 1
                tmp_var = f"__struct_tmp_{self.tmp_var_counter}"
                lines = [f"const {tmp_var} = {val_str};"]
                kw = "var" if stmt.is_mutable else "const"
                for fitem in fields:
                    if ":" in fitem:
                        fname, vname = fitem.split(":", 1)
                        fname = fname.strip()
                        vname = vname.replace("mut ", "").strip()
                    else:
                        fname = fitem.replace("mut ", "").strip()
                        vname = fname
                    clean_vname = f'@"{vname}"' if vname in ZIG_RESERVED_KEYWORDS else vname
                    clean_fname = f'@"{fname}"' if fname in ZIG_RESERVED_KEYWORDS else fname
                    if clean_vname == "_":
                        lines.append(f"_ = {tmp_var}.{clean_fname};")
                    else:
                        lines.append(f"{kw} {clean_vname} = {tmp_var}.{clean_fname};")
                return f"\n{self._indent()}".join(lines)
            kw = "var" if stmt.is_mutable else "const"
            vname = stmt.name
            was_renamed = False
            if vname in getattr(self, "current_fn_param_names", set()):
                vname = f"{vname}_var"
                was_renamed = True
            vname = f'@"{vname}"' if (vname in ZIG_RESERVED_KEYWORDS and not vname.startswith("@")) else vname
            type_part = f": {map_type(stmt.var_type)}" if stmt.var_type else ""
            val_expr_str = self._emit_expr(stmt.value).rstrip(";").strip() if stmt.value else ""
            val_part = f" = {val_expr_str}" if stmt.value else ""
            res = f"{kw} {vname}{type_part}{val_part};"
            if was_renamed:
                res += f"\n{self._indent()}_ = {vname};"
            if stmt.name == "ip":
                res += f"\n{self._indent()}_ = ip;"
            return res

        if isinstance(stmt, AssignStmt):
            lhs_str = self._emit_expr(stmt.lhs)
            rhs_str = self._emit_expr(stmt.rhs)
            if lhs_str == "_" and "," in rhs_str:
                raw_rhs = rhs_str.lstrip(".{(").rstrip("})")
                items = [it.strip() for it in raw_rhs.split(",") if it.strip()]
                return f"\n{self._indent()}".join(f"_ = {it};" for it in items)
            return f"{lhs_str} {stmt.op} {rhs_str};"

        if isinstance(stmt, ExprStmt):
            expr_str = self._emit_expr(stmt.expr)
            if expr_str.startswith("_ = ") and "," in expr_str:
                raw_rhs = expr_str[4:].strip().rstrip(";")
                raw_rhs = raw_rhs.lstrip(".{(").rstrip("})")
                items = [it.strip() for it in raw_rhs.split(",") if it.strip()]
                return f"\n{self._indent()}".join(f"_ = {it};" for it in items)
            if isinstance(stmt.expr, (IfExpr, LoopExpr, MatchExpr)):
                return expr_str
            if expr_str.startswith("{") and expr_str.endswith("}") and not isinstance(stmt.expr, (ReturnExpr, AssignStmt, CallExpr, StructInitExpr)):
                return expr_str
            return f"{expr_str};"

        if isinstance(stmt, StructDecl):
            return self._emit_struct(stmt, [])

        if isinstance(stmt, EnumDecl):
            return self._emit_enum(stmt)

        if isinstance(stmt, FnDecl):
            return self._emit_function(stmt)

        return ""

    def _emit_expr(self, expr: Expr) -> str:
        """Emit expression string."""
        if isinstance(expr, str):
            return expr

        if isinstance(expr, LiteralExpr):
            val = expr.value
            if val.startswith('b"') and val.endswith('"'):
                val = val[1:]
            elif val.startswith("b'") and val.endswith("'"):
                val = val[1:]
            if (val.startswith("r") or val.startswith("br")) and '"' in val:
                val = re.sub(r'^(?:b?r)#*"(.*)"#*$', r'"\1"', val)
            if val.startswith('"') and val.endswith('"'):
                if "\n" in val:
                    inner = val[1:-1].replace("\r\n", "\\n").replace("\n", "\\n")
                    val = f'"{inner}"'
            if val.startswith("[") and ";" in val and val.endswith("]"):
                inner = val[1:-1]
                vpart, cpart = inner.split(";", 1)
                vpart = vpart.strip().replace("_u8", "").replace("u8", "")
                cpart = cpart.strip()
                return f"([_]u8{{{vpart}}} ** {cpart})"
            if expr.kind == "bool":
                return expr.value.lower()
            res = re.sub(r"_?(u8|u16|u32|u64|u128|usize|i8|i16|i32|i64|i128|isize|f32|f64)$", "", val)
            if res.endswith(".") and res[:-1].lstrip("-").isdigit():
                res += "0"
            return res

        if isinstance(expr, IdentifierExpr):
            name = expr.name
            if name.endswith(".") and name[:-1].lstrip("-").isdigit():
                name += "0"
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
                    escaped_parts = [f'@"{p}"' if (p in ZIG_RESERVED_KEYWORDS and not p.startswith("@")) else p for p in parts]
                    return ".".join(escaped_parts)
                if len(parts) > 1 and parts[1][0].islower():
                    if parts[0] in ("Transform", "Velocity", "Time", "App", "Commands"):
                        return f"bevy_ecs.{parts[0]}.{parts[1]}"
                    escaped_parts = [f'@"{p}"' if (p in ZIG_RESERVED_KEYWORDS and not p.startswith("@")) else p for p in parts]
                    return f"{escaped_parts[0]}.{escaped_parts[1]}"
                return f".{parts[-1]}"
            if name == "Some":
                return ""
            if name == "None":
                return "null"
            if name == "Self":
                return "@This()"
            if name in ZIG_RESERVED_KEYWORDS and not name.startswith("@") and not name.startswith("std.") and not name.startswith("*"):
                return f'@"{name}"'
            if re.search(r'(?<!\.)\.\d+\b', name):
                name = re.sub(r'(?<!\.)\.(\d+)\b', r'.@"\1"', name)
            return name

        if isinstance(expr, BinaryExpr):
            left_str = self._emit_expr(expr.left)
            right_str = self._emit_expr(expr.right)
            if expr.op == "as":
                mapped_target = map_type(right_str)
                if mapped_target.startswith("*") or mapped_target == "_" or right_str in ("_", "*mut _", "*const _"):
                    return f"@ptrCast({left_str})"
                return f"@as({mapped_target}, {left_str})"
            if expr.op in ("=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="):
                return f"{left_str} {expr.op} {right_str}"
            op_map = {"&&": "and", "||": "or"}
            op = op_map.get(expr.op, expr.op)
            return f"({left_str} {op} {right_str})"

        if isinstance(expr, UnaryExpr):
            op_map = {"!": "!", "-": "-", "*": ".*", "&": "&", "&mut": "&"}
            zop = op_map.get(expr.op, expr.op)
            operand_str = self._emit_expr(expr.operand)
            if operand_str.startswith("mut "):
                operand_str = operand_str[4:]
            if zop == "&" and operand_str.startswith("[") and operand_str.endswith("]"):
                return f"&.{{{operand_str[1:-1]}}}"
            if zop == "!" and not (operand_str in ("true", "false") or operand_str.startswith("is_") or operand_str.startswith("has_") or operand_str.startswith("can_")):
                zop = "~"
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
            args_list = []
            for arg in expr.args:
                arg_str = self._emit_expr(arg)
                if arg_str == "()":
                    arg_str = "{}"
                args_list.append(arg_str)
            args_str = ", ".join(args_list)
            return f"{callee_str}({args_str})"

        if isinstance(expr, FieldAccessExpr):
            target_str = self._emit_expr(expr.target)
            fname = expr.field_name
            if fname == "await":
                return target_str
            if (fname.isdigit() or fname in ZIG_RESERVED_KEYWORDS) and not fname.startswith("@"):
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
            formatted_fields = []
            for f in expr.fields:
                raw_fname = f.field_name.replace("r#", "")
                fname = f'@"{raw_fname}"' if (raw_fname in ZIG_KEYWORDS_AND_PRIMITIVES or not raw_fname.isidentifier()) and not raw_fname.isdigit() else raw_fname
                val_str = self._emit_expr(f.value)
                formatted_fields.append(f".{fname} = {val_str}")
            fields_str = ", ".join(formatted_fields)
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
            if not expr.value:
                return "return"
            val_str = self._emit_expr(expr.value).strip()
            if val_str in (".{}", "()", "void", "Ok()", "Ok({})"):
                return "return"
            if val_str.startswith("(") and val_str.endswith(")"):
                val_str = val_str[1:-1].strip()
            return f"return {val_str}" if val_str else "return"

        if isinstance(expr, MatchExpr):
            target_str = self._emit_expr(expr.target)
            lines: List[str] = [f"switch ({target_str}) {{"]
            self.current_indent += 1

            has_else = False
            for arm in expr.arms:
                pat_str = arm.pattern.strip()
                if "{" in pat_str and "}" in pat_str:
                    pat_str = re.sub(r"\s*\{\s*\.\.\s*\}", "", pat_str).strip()
                guard_cond: Optional[str] = None
                if " if " in pat_str:
                    pat_clean, _, guard_part = pat_str.partition(" if ")
                    pat_str = pat_clean.strip()
                    guard_cond = guard_part.strip()
                elif arm.guard:
                    guard_cond = self._emit_expr(arm.guard)

                if pat_str == "_":
                    pat = "else"
                elif pat_str.startswith("Ok(") or pat_str.startswith("Some("):
                    var_name = pat_str[pat_str.find("(")+1:pat_str.rfind(")")].strip()
                    pat = f"else => |{var_name}|" if (var_name and var_name != "_") else "else"
                elif pat_str.startswith("Err(") or pat_str == "None":
                    var_name = pat_str[pat_str.find("(")+1:pat_str.rfind(")")].strip() if "(" in pat_str else ""
                    pat = "else" if not has_else else "error.Unknown"
                elif "::" in pat_str:
                    clean_enum_variant = re.sub(r"\(\s*\.\.\s*\)", "", pat_str.split("::")[-1]).strip()
                    pat = f".{clean_enum_variant}"
                else:
                    pat = pat_str

                if pat.startswith("else"):
                    if has_else:
                        continue
                    has_else = True

                body_str = self._emit_expr(arm.body)
                if body_str.rstrip(";").strip() in ("()", ".{}"):
                    body_str = "{}"
                if guard_cond:
                    if body_str == "{}":
                        body_str = f"if ({guard_cond}) {{}}"
                    else:
                        body_str = f"if ({guard_cond}) {body_str} else {{}}"

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
                        cap_var = pat_part.split("(", 1)[1].rstrip(")").lstrip("(").strip().replace("ref mut ", "").replace("ref ", "").replace("mut ", "").strip()
                        if "," in cap_var or not cap_var.isidentifier():
                            cap_var = "item"
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
                cap_var = expr.var_name
                if "let " in cond_str and "=" in cond_str:
                    clean_cond = cond_str
                    if clean_cond.startswith("(") and clean_cond.endswith(")"):
                        clean_cond = clean_cond[1:-1]
                    if clean_cond.startswith("let "):
                        parts = clean_cond[4:].split("=", 1)
                        pat_part = parts[0].strip()
                        cond_str = parts[1].strip() if len(parts) > 1 else cond_str
                        if not cap_var and "(" in pat_part and ")" in pat_part:
                            cap_var = pat_part.split("(", 1)[1].rstrip(")").lstrip("(").strip().replace("ref mut ", "").replace("ref ", "").replace("mut ", "").strip()
                            if "," in cap_var or not cap_var.isidentifier():
                                cap_var = "item"
                capture_str = f" |{cap_var}|" if cap_var else ""
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
            params_parts = []
            param_names = []
            for idx, p in enumerate(expr.params):
                ptype = map_type(p.param_type) if (p.param_type and p.param_type.name != "anytype") else "anytype"
                raw_name = p.name.split(":")[0].strip() if p.name else ""
                pname = raw_name.replace("(", "").replace(")", "").replace(" ", "_").replace("&", "").strip() if raw_name else f"arg{idx}"
                if "," in pname or not pname.isidentifier() or pname == "_":
                    pname = f"arg{idx}"
                if pname in ZIG_RESERVED_KEYWORDS and not pname.startswith("@"):
                    pname = f'@"{pname}"'
                params_parts.append(f"{pname}: {ptype}")
                param_names.append(pname)
            params_str = ", ".join(params_parts)
            if expr.return_type:
                ret_type = map_type(expr.return_type)
            elif isinstance(expr.body, BlockExpr) and not expr.body.trailing_expr and not any(isinstance(s, ReturnExpr) and s.value for s in expr.body.stmts):
                ret_type = "void"
            else:
                ret_type = "i32"

            if isinstance(expr.body, BlockExpr):
                body_lines = self._emit_block_lines(expr.body)
                body_text = "\n".join(body_lines)
                discard_lines = []
                for pname in param_names:
                    if pname and pname != "_" and not pname.startswith("_") and not pname.startswith("arg"):
                        clean_search = pname.strip('"@')
                        if not re.search(r"\b" + re.escape(clean_search) + r"\b", body_text):
                            discard_lines.append(f"{self._indent()}_ = {pname};")
                lines = [f"(struct {{ fn run({params_str}) {ret_type} {{"]
                self.current_indent += 1
                lines.extend(discard_lines)
                lines.extend(body_lines)
                self.current_indent -= 1
                lines.append(f"{self._indent()}}} }}.run)")
                return "\n".join(lines)
            else:
                body_str = self._emit_expr(expr.body)
                discard_prefix = ""
                for pname in param_names:
                    if pname and pname != "_" and not pname.startswith("_") and not pname.startswith("arg"):
                        clean_search = pname.strip('"@')
                        if not re.search(r"\b" + re.escape(clean_search) + r"\b", body_str):
                            discard_prefix += f"_ = {pname}; "
                return f"(struct {{ fn run({params_str}) {ret_type} {{ {discard_prefix}return {body_str}; }} }}.run)"

        return "{}"


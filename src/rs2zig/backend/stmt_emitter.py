"""
Statement Emitter for rs2zig Backend.
"""

import re
from typing import Any, List
from rs2zig.ir.nodes import (
    BlockExpr, Stmt, LetStmt, AssignStmt, ExprStmt, FnDecl, StructDecl, EnumDecl,
    IfExpr, LoopExpr, MatchExpr, ReturnExpr, CallExpr, StructInitExpr
)
from rs2zig.lowering.stdlib_map import map_type
from rs2zig.backend.emitter_constants import ZIG_RESERVED_KEYWORDS


def emit_block_lines(block: BlockExpr, emitter_ctx: Any) -> List[str]:
    """Emit list of indented statement strings inside a block.

    Args:
        block: Block expression node.
        emitter_ctx: ZigEmitter context reference.

    Returns:
        List of formatted statement lines.
    """
    prev_vars = getattr(emitter_ctx, "current_block_vars", None)
    emitter_ctx.current_block_vars = set()
    try:
        lines: List[str] = []
        for stmt in block.stmts:
            stmt_str = emit_stmt(stmt, emitter_ctx)
            if stmt_str and stmt_str.strip() != ";":
                lines.append(f"{emitter_ctx._indent()}{stmt_str}")

        if block.trailing_expr:
            expr_str = emitter_ctx._emit_expr(block.trailing_expr)
            if expr_str.strip() in ("()", ".{}", "void"):
                lines.append(f"{emitter_ctx._indent()}return;")
            else:
                lines.append(f"{emitter_ctx._indent()}return {expr_str};")

        full_text = "\n".join(lines)
        final_lines: List[str] = []
        for i, line in enumerate(lines):
            final_lines.append(line)
            for sub_line in line.splitlines():
                stripped = sub_line.strip()
                if (stripped.startswith("const ") or stripped.startswith("var ")) and "=" in stripped:
                    parts = stripped.split()
                    if len(parts) >= 2:
                        raw_v = parts[1].split(":")[0].split("=")[0].strip().strip('";@')
                        if raw_v and raw_v != "_" and raw_v.isidentifier():
                            pos = full_text.find(sub_line)
                            subsequent = full_text[pos + len(sub_line):] if pos != -1 else "\n".join(lines[i+1:])
                            if stripped.startswith("var "):
                                has_mut = (
                                    re.search(r"\b" + re.escape(raw_v) + r"\b\s*(?:\.[a-zA-Z0-9_@]+)*\s*(?:[\+\-\*\/\%\&\|\^\<\>]?=|=(?![=>]))", subsequent)
                                    or re.search(r"&\s*" + re.escape(raw_v) + r"\b", subsequent)
                                    or re.search(r"\b" + re.escape(raw_v) + r"\.(?:append|push|insert|clear|add|remove|update|set|put|swap|extend|write|mut)\b", subsequent)
                                )
                                if not has_mut:
                                    final_lines[-1] = final_lines[-1].replace("var " + raw_v, "const " + raw_v, 1)
                            if not re.search(r"\b" + re.escape(raw_v) + r"\b", subsequent):
                                indent = line[: len(line) - len(line.lstrip())]
                                clean_ident = f'@"{raw_v}"' if raw_v in ZIG_RESERVED_KEYWORDS else raw_v
                                final_lines.append(f"{indent}_ = {clean_ident};")

        return final_lines
    finally:
        emitter_ctx.current_block_vars = prev_vars


def emit_stmt(stmt: Stmt, emitter_ctx: Any) -> str:
    """Emit single statement string without leading indent.

    Args:
        stmt: Statement IR node.
        emitter_ctx: ZigEmitter context reference.

    Returns:
        Formatted Zig statement string.
    """
    if isinstance(stmt, FnDecl):
        fn_code = emitter_ctx._emit_function(stmt)
        if getattr(emitter_ctx, "current_fn", None) is not None or emitter_ctx.current_indent > 0:
            return f"const {stmt.name} = (struct {{ {fn_code} }}).{stmt.name};"
        return fn_code

    if isinstance(stmt, LetStmt):
        if stmt.name == "_":
            val_str = emitter_ctx._emit_expr(stmt.value) if stmt.value else "0"
            return f"_ = {val_str};"
        if stmt.name.startswith("Some(") or stmt.name.startswith("Ok("):
            prefix_len = 5 if stmt.name.startswith("Some(") else 3
            inner_pat = stmt.name[prefix_len:-1].strip()
            val_str = emitter_ctx._emit_expr(stmt.value) if stmt.value else "null"
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
                return f"\n{emitter_ctx._indent()}".join(lines)
            else:
                clean_vname = inner_pat.replace("mut ", "").strip()
                kw = "var" if stmt.is_mutable else "const"
                return f"{kw} {clean_vname} = {val_str} orelse return;"

        if stmt.name.startswith("(") and stmt.name.endswith(")"):
            vars_str = stmt.name[1:-1]
            var_list = [v.strip() for v in vars_str.split(",") if v.strip()]
            val_str = emitter_ctx._emit_expr(stmt.value) if stmt.value else "undefined"
            emitter_ctx.tmp_var_counter += 1
            tmp_var = f"__tuple_tmp_{emitter_ctx.tmp_var_counter}"
            lines = [f"const {tmp_var} = {val_str};"]
            kw = "var" if stmt.is_mutable else "const"
            for idx, vname in enumerate(var_list):
                clean_vname = vname.replace("mut ", "").strip()
                if clean_vname == "_":
                    lines.append(f"_ = {tmp_var}.@\"{idx}\";")
                else:
                    lines.append(f"{kw} {clean_vname} = {tmp_var}.@\"{idx}\";")
            return f"\n{emitter_ctx._indent()}".join(lines)

        if "{" in stmt.name and "}" in stmt.name:
            body = stmt.name[stmt.name.find("{") + 1 : stmt.name.rfind("}")].strip()
            fields = [f.strip() for f in body.split(",") if f.strip()]
            val_str = emitter_ctx._emit_expr(stmt.value) if stmt.value else "undefined"
            emitter_ctx.tmp_var_counter += 1
            tmp_var = f"__struct_tmp_{emitter_ctx.tmp_var_counter}"
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
            return f"\n{emitter_ctx._indent()}".join(lines)

        kw = "var" if stmt.is_mutable else "const"
        vname = stmt.name
        is_dedup = False
        if hasattr(emitter_ctx, "current_block_vars") and emitter_ctx.current_block_vars is not None:
            if vname in emitter_ctx.current_block_vars:
                vname = f"{vname}_alt"
                is_dedup = True
            else:
                emitter_ctx.current_block_vars.add(vname)
        was_renamed = False
        if vname in getattr(emitter_ctx, "current_fn_param_names", set()):
            vname = f"{vname}_var"
            was_renamed = True
        vname = f'@"{vname}"' if (vname in ZIG_RESERVED_KEYWORDS and not vname.startswith("@")) else vname
        type_part = f": {map_type(stmt.var_type)}" if stmt.var_type else ""
        val_expr_str = emitter_ctx._emit_expr(stmt.value).rstrip(";").strip() if stmt.value else ""
        if val_expr_str.startswith("{") and not val_expr_str.endswith("}"):
            val_expr_str = f"({val_expr_str})"
        val_part = f" = {val_expr_str}" if stmt.value else ""
        res = f"{kw} {vname}{type_part}{val_part};"
        clean_vname = vname.strip('"@')
        if was_renamed or is_dedup or (clean_vname.startswith("_") and clean_vname != "_"):
            res += f"\n{emitter_ctx._indent()}_ = {vname};"
        if stmt.name == "ip":
            res += f"\n{emitter_ctx._indent()}_ = ip;"
        return res

    if isinstance(stmt, AssignStmt):
        lhs_str = emitter_ctx._emit_expr(stmt.lhs)
        rhs_str = emitter_ctx._emit_expr(stmt.rhs)
        if lhs_str == "_" and "," in rhs_str:
            raw_rhs = rhs_str.lstrip(".{(").rstrip("})")
            items = [it.strip() for it in raw_rhs.split(",") if it.strip()]
            return f"\n{emitter_ctx._indent()}".join(f"_ = {it};" for it in items)
        return f"{lhs_str} {stmt.op} {rhs_str};"

    if isinstance(stmt, ExprStmt):
        expr_str = emitter_ctx._emit_expr(stmt.expr).rstrip(";").strip()
        if not expr_str:
            return ""
        if expr_str.startswith("_ = ") and "," in expr_str:
            raw_rhs = expr_str[4:].strip().rstrip(";")
            raw_rhs = raw_rhs.lstrip(".{(").rstrip("})")
            items = [it.strip() for it in raw_rhs.split(",") if it.strip()]
            return f"\n{emitter_ctx._indent()}".join(f"_ = {it};" for it in items)
        if isinstance(stmt.expr, (IfExpr, LoopExpr, MatchExpr)):
            return expr_str
        if expr_str.startswith("{") and expr_str.endswith("}") and not isinstance(stmt.expr, (ReturnExpr, AssignStmt, CallExpr, StructInitExpr)):
            return expr_str
        if expr_str.startswith("{") and not expr_str.endswith("}"):
            expr_str = f"({expr_str})"
        return f"{expr_str};"

    if isinstance(stmt, StructDecl):
        return emitter_ctx._emit_struct(stmt, [])

    if isinstance(stmt, EnumDecl):
        return emitter_ctx._emit_enum(stmt)

    if isinstance(stmt, FnDecl):
        return emitter_ctx._emit_function(stmt)

    return ""

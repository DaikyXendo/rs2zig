"""
Expression Emitter for rs2zig Backend.
"""

import re
from typing import Any, List, Optional
from rs2zig.ir.nodes import (
    Expr, LiteralExpr, IdentifierExpr, BinaryExpr, UnaryExpr, CallExpr,
    FieldAccessExpr, StructInitExpr, MacroCallExpr, ReturnExpr, IfExpr,
    LoopExpr, MatchExpr, TryExpr, OptionalUnwrapExpr, ClosureExpr, BlockExpr, TypeNode
)
from rs2zig.lowering.stdlib_map import map_type
from rs2zig.lowering.control_flow import lower_println_macro
from rs2zig.backend.emitter_constants import ZIG_RESERVED_KEYWORDS, ZIG_KEYWORDS_AND_PRIMITIVES


def emit_expr(expr: Expr, emitter_ctx: Any) -> str:
    """Emit expression string.

    Args:
        expr: Expression IR node.
        emitter_ctx: Reference to ZigEmitter context.

    Returns:
        Formatted Zig expression string.
    """
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
            if "\\0" in val:
                val = val.replace("\\0", "\\x00")
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
            base_str = emit_expr(IdentifierExpr(name=base), emitter_ctx)
            gen_type = map_type(gen_part.strip()) if gen_part.strip() else "void"
            name = f"{base_str}({gen_type}){trailing}"
        if "::" in name:
            parts = [p.strip() for p in name.split("::") if p.strip()]
            if not parts:
                return name
            if parts[0] in ("bevy", "std", "bevy_ecs"):
                return ".".join(parts)
            if parts[0] in ("Some", "Ok"):
                return parts[1]
            if parts[0] == "None":
                return "null"
            if parts[0] == "Err":
                err_clean = parts[1].lstrip(".")
                if err_clean.startswith("error."):
                    return err_clean
                return f"error.{err_clean}"
            if parts[0][0].islower() and parts[0].isidentifier():
                if parts[0] not in ("self", "super", "crate", "std", "bevy", "bevy_ecs"):
                    emitter_ctx.imported_modules.add(parts[0])
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
        left_str = emit_expr(expr.left, emitter_ctx)
        right_str = emit_expr(expr.right, emitter_ctx)
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
        operand_str = emit_expr(expr.operand, emitter_ctx)
        if operand_str.startswith("mut "):
            operand_str = operand_str[4:]
        if zop == "&" and operand_str.startswith("[") and operand_str.endswith("]"):
            return f"&.{{{operand_str[1:-1]}}}"
        if zop == "!" and not (operand_str in ("true", "false") or operand_str.startswith("is_") or operand_str.startswith("has_") or operand_str.startswith("can_")):
            zop = "~"
        return f"({zop}{operand_str})" if zop != ".*" else f"({operand_str}.*)"

    if isinstance(expr, TryExpr):
        op_str = emit_expr(expr.operand, emitter_ctx)
        return f"try {op_str}"

    if isinstance(expr, OptionalUnwrapExpr):
        op_str = emit_expr(expr.operand, emitter_ctx)
        return f"({op_str} orelse unreachable)"

    if isinstance(expr, CallExpr):
        callee_str = emit_expr(expr.callee, emitter_ctx)
        if callee_str in ("Some", "Ok"):
            return emit_expr(expr.args[0], emitter_ctx) if expr.args else "null"
        if callee_str == "Err":
            err_val = emit_expr(expr.args[0], emitter_ctx) if expr.args else "UnknownError"
            err_clean = err_val.strip('"').lstrip(".")
            if err_clean.startswith("error."):
                return err_clean
            return f"error.{err_clean}"
        if callee_str in ZIG_KEYWORDS_AND_PRIMITIVES:
            callee_str = f'@"{callee_str}"'
        args_list = []
        for arg in expr.args:
            arg_str = emit_expr(arg, emitter_ctx)
            if arg_str == "()":
                arg_str = "{}"
            args_list.append(arg_str)
        args_str = ", ".join(args_list)
        return f"{callee_str}({args_str})"

    if isinstance(expr, FieldAccessExpr):
        target_str = emit_expr(expr.target, emitter_ctx)
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
            val_str = emit_expr(f.value, emitter_ctx)
            formatted_fields.append(f".{fname} = {val_str}")
        fields_str = ", ".join(formatted_fields)
        if "::" in s_name:
            parts = s_name.split("::")
            if len(parts) >= 2 and parts[-1][0].isupper():
                return f".{{ .{parts[-1]} = .{{ {fields_str} }} }}"
            return f".{{ {fields_str} }}"
        if expr.struct_name == ".":
            if all(f.field_name.isdigit() for f in expr.fields):
                elems_str = ", ".join(emit_expr(f.value, emitter_ctx) for f in expr.fields)
                return f".{{{elems_str}}}"
            else:
                return f".{{ {fields_str} }}"
        return f"{s_name}{{ {fields_str} }}"

    if isinstance(expr, MacroCallExpr):
        if expr.macro_name in ("println", "print"):
            fmt_str, args = lower_println_macro(expr)
            args_parts = ", ".join(emit_expr(a, emitter_ctx) for a in args)
            return f'std.debug.print("{fmt_str}", .{{{args_parts}}})'
        if expr.macro_name == "matches":
            if len(expr.args) >= 2:
                target_str = emit_expr(expr.args[0], emitter_ctx)
                pat_str = emit_expr(expr.args[1], emitter_ctx)
                if pat_str.startswith("."):
                    pass
                elif "::" in pat_str:
                    pat_str = f".{pat_str.split('::')[-1]}"
                return f"(switch ({target_str}) {{ {pat_str} => true, else => false }})"
            return "true"

    if isinstance(expr, ReturnExpr):
        if not expr.value:
            return "return"
        val_str = emit_expr(expr.value, emitter_ctx).strip()
        if val_str in (".{}", "()", "void", "Ok()", "Ok({})"):
            return "return"
        if val_str.startswith("(") and val_str.endswith(")"):
            val_str = val_str[1:-1].strip()
        return f"return {val_str}" if val_str else "return"

    if isinstance(expr, MatchExpr):
        target_str = emit_expr(expr.target, emitter_ctx)
        lines: List[str] = [f"switch ({target_str}) {{"]
        emitter_ctx.current_indent += 1

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
                guard_cond = emit_expr(arm.guard, emitter_ctx)

            if pat_str == "_":
                pat = "else"
            elif pat_str.startswith("Ok(") or pat_str.startswith("Some("):
                var_name = pat_str[pat_str.find("(")+1:pat_str.rfind(")")].strip()
                pat = f"else => |{var_name}|" if (var_name and var_name != "_") else "else"
            elif pat_str.startswith("Err(") or pat_str == "None":
                var_name = pat_str[pat_str.find("(")+1:pat_str.rfind(")")].strip() if "(" in pat_str else ""
                pat = "else" if not has_else else "error.Unknown"
            elif pat_str.startswith("(") and pat_str.endswith(")"):
                inner = pat_str[1:-1].strip()
                if "," in inner:
                    raw_items = [p.strip() for p in inner.split(",") if p.strip()]
                    mapped_items = []
                    for it in raw_items:
                        if "::" in it:
                            mapped_items.append(f".{it.split('::')[-1]}")
                        else:
                            mapped_items.append(it)
                    pat = f".{{ {', '.join(mapped_items)} }}"
                elif "::" in inner:
                    pat = f".{inner.split('::')[-1]}"
                else:
                    pat = pat_str
            elif "(" in pat_str and ")" in pat_str:
                variant_part = pat_str[:pat_str.find("(")].strip()
                if "::" in variant_part:
                    variant_part = variant_part.split("::")[-1]
                variant_name = variant_part.lstrip(".")
                if not variant_name:
                    pat = pat_str
                else:
                    cap_var = pat_str[pat_str.find("(")+1:pat_str.rfind(")")].strip().replace("ref mut ", "").replace("ref ", "").replace("mut ", "").strip()
                    if cap_var and cap_var.isidentifier() and cap_var != "_":
                        pat = f".{variant_name} => |{cap_var}|"
                    else:
                        pat = f".{variant_name}"
            elif "::" in pat_str:
                clean_enum_variant = re.sub(r"\(\s*\.\.\s*\)", "", pat_str.split("::")[-1]).strip()
                pat = f".{clean_enum_variant}"
            else:
                pat = pat_str

            if pat.startswith("else"):
                if has_else:
                    continue
                has_else = True

            body_str = emit_expr(arm.body, emitter_ctx)
            if body_str.rstrip(";").strip() in ("()", ".{}"):
                body_str = "{}"
            if guard_cond:
                if body_str == "{}":
                    body_str = f"if ({guard_cond}) {{}}"
                else:
                    body_str = f"if ({guard_cond}) {body_str} else {{}}"

            if pat.startswith("else =>") or "=> |" in pat:
                lines.append(f"{emitter_ctx._indent()}{pat} {body_str},")
            else:
                lines.append(f"{emitter_ctx._indent()}{pat} => {body_str},")

        emitter_ctx.current_indent -= 1
        lines.append(f"{emitter_ctx._indent()}}}")
        return "\n".join(lines)

    if isinstance(expr, IfExpr):
        cond_str = emit_expr(expr.condition, emitter_ctx)
        lines = []
        if "=" in cond_str and not any(op in cond_str for op in ("==", "!=", "<=", ">=")) and not cond_str.startswith("if "):
            clean_cond = cond_str
            if clean_cond.startswith("(") and clean_cond.endswith(")"):
                clean_cond = clean_cond[1:-1]
            clean_cond = clean_cond.replace("let ", "").strip()
            if "=" in clean_cond and not any(op in clean_cond for op in ("==", "!=", "<=", ">=")):
                parts = clean_cond.split("=", 1)
                pat_part = parts[0].strip()
                target_part = parts[1].strip()
                cap_var = "item"
                if "(" in pat_part and ")" in pat_part:
                    cap_var = pat_part[pat_part.find("(")+1:pat_part.rfind(")")].strip().replace("ref mut ", "").replace("ref ", "").replace("mut ", "").strip()
                    if "," in cap_var or not cap_var.isidentifier():
                        cap_var = "item"
                if pat_part.startswith("Err"):
                    lines = [f"_ = {target_part} catch |{cap_var}| {{", f"{emitter_ctx.indent_str * (emitter_ctx.current_indent + 1)}_ = {cap_var};"]
                else:
                    lines = [f"if ({target_part}) |{cap_var}| {{"]

        if not lines:
            lines = [f"if ({cond_str}) {{"]
        emitter_ctx.current_indent += 1
        lines.extend(emitter_ctx._emit_block_lines(expr.then_block))
        emitter_ctx.current_indent -= 1

        if expr.else_block:
            if isinstance(expr.else_block, BlockExpr):
                lines.append(f"{emitter_ctx._indent()}}} else {{")
                emitter_ctx.current_indent += 1
                lines.extend(emitter_ctx._emit_block_lines(expr.else_block))
                emitter_ctx.current_indent -= 1
                lines.append(f"{emitter_ctx._indent()}}}")
            elif isinstance(expr.else_block, IfExpr):
                lines.append(f"{emitter_ctx._indent()}}} else {emit_expr(expr.else_block, emitter_ctx)}")
        else:
            closing = "};" if lines[0].startswith("_ = ") else "}"
            lines.append(f"{emitter_ctx._indent()}{closing}")
        return "\n".join(lines)

    if isinstance(expr, LoopExpr):
        if expr.loop_kind == "while" and expr.condition:
            cond_str = emit_expr(expr.condition, emitter_ctx)
            cap_var = expr.var_name
            if "let " in cond_str and "=" in cond_str:
                clean_cond = cond_str
                if clean_cond.startswith("(") and clean_cond.endswith(")"):
                    clean_cond = clean_cond[1:-1]
                if clean_cond.startswith("let "):
                    parts = clean_cond[4:].split("=", 1)
                    pat_part = parts[0].strip()
                    cond_str = parts[1].strip() if len(parts) > 1 else cond_str
                    if cond_str.endswith("?"):
                        cond_str = f"try {cond_str[:-1]}"
                    if not cap_var and "(" in pat_part and ")" in pat_part:
                        cap_var = pat_part.split("(", 1)[1].rstrip(")").lstrip("(").strip().replace("ref mut ", "").replace("ref ", "").replace("mut ", "").strip()
                        if "," in cap_var or not cap_var.isidentifier():
                            cap_var = "item"
            if cond_str.endswith("?"):
                cond_str = f"try {cond_str[:-1]}"
            capture_str = f" |{cap_var}|" if cap_var else ""
            lines = [f"while ({cond_str}){capture_str} {{"]
            emitter_ctx.current_indent += 1
            lines.extend(emitter_ctx._emit_block_lines(expr.body))
            emitter_ctx.current_indent -= 1
            lines.append(f"{emitter_ctx._indent()}}}")
            return "\n".join(lines)
        elif expr.loop_kind == "loop":
            lines = ["while (true) {"]
            emitter_ctx.current_indent += 1
            lines.extend(emitter_ctx._emit_block_lines(expr.body))
            emitter_ctx.current_indent -= 1
            lines.append(f"{emitter_ctx._indent()}}}")
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
            body_lines = emitter_ctx._emit_block_lines(expr.body)
            body_text = "\n".join(body_lines)
            discard_lines = [
                f"{emitter_ctx._indent()}_ = {pname};"
                for pname in param_names
                if pname and pname != "_"
                and not re.search(r"\b" + re.escape(pname.strip('"@')) + r"\b", body_text)
            ]
            lines = [f"(struct {{ fn run({params_str}) {ret_type} {{"]
            emitter_ctx.current_indent += 1
            lines.extend(discard_lines)
            lines.extend(body_lines)
            emitter_ctx.current_indent -= 1
            lines.append(f"{emitter_ctx._indent()}}} }}.run)")
            return "\n".join(lines)
        else:
            body_str = emit_expr(expr.body, emitter_ctx)
            discards = [
                f"_ = {pname}; " for pname in param_names
                if pname and pname != "_"
                and not re.search(r"\b" + re.escape(pname.strip('"@')) + r"\b", body_str)
            ]
            discard_prefix = "".join(discards)
            return f"(struct {{ fn run({params_str}) {ret_type} {{ {discard_prefix}return {body_str}; }} }}.run)"

    return "{}"

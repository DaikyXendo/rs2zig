"""
Declaration Emitter Helpers for rs2zig Backend.
"""

import re
from typing import List, Callable, Optional, Set, Any
from rs2zig.ir.nodes import TraitDecl, EnumDecl, StructDecl, FnDecl, Param, TypeNode
from rs2zig.lowering.stdlib_map import map_type
from rs2zig.backend.emitter_constants import ZIG_RESERVED_KEYWORDS, ZIG_KEYWORDS_AND_PRIMITIVES


def emit_trait_decl(trait: TraitDecl) -> str:
    """Emit Zig interface definition / comment for a trait."""
    vis = "pub " if trait.is_pub else ""
    tname = trait.name.split("<")[0].strip() if "<" in trait.name else trait.name
    lines: List[str] = [f"// Trait: {trait.name}"]
    lines.append(f"{vis}const {tname} = struct {{}};")
    return "\n".join(lines)


def emit_enum_decl(enum_decl: EnumDecl, indent_fn: Callable[[], str], inc_indent: Callable[[], None], dec_indent: Callable[[], None]) -> str:
    """Emit Zig enum or tagged union definition."""
    vis = "pub " if enum_decl.is_pub else ""
    ename = enum_decl.name.split("<")[0].strip() if "<" in enum_decl.name else enum_decl.name
    has_payload = any(len(v.fields) > 0 for v in enum_decl.variants)
    header = f"{vis}const {ename} = union(enum) {{" if has_payload else f"{vis}const {ename} = enum {{"

    lines: List[str] = [header]
    inc_indent()

    for v in enum_decl.variants:
        if not has_payload or len(v.fields) == 0:
            lines.append(f"{indent_fn()}{v.name},")
        else:
            if len(v.fields) == 1 and v.fields[0].name is None:
                ftype = map_type(v.fields[0].field_type)
                lines.append(f"{indent_fn()}{v.name}: {ftype},")
            else:
                field_specs = []
                for f in v.fields:
                    fname = f.name or "val"
                    ftype = map_type(f.field_type)
                    field_specs.append(f"{fname}: {ftype}")
                lines.append(f"{indent_fn()}{v.name}: struct {{ {', '.join(field_specs)} }},")

    dec_indent()
    lines.append("};")
    return "\n".join(lines)


def emit_struct_decl(struct: StructDecl, methods: List[FnDecl], emitter_ctx: Any) -> str:
    """Emit Zig struct definition including any impl methods."""
    vis = "pub " if struct.is_pub else ""
    sname = struct.name.split("<")[0].strip() if "<" in struct.name else struct.name
    type_params = [g.name for g in getattr(struct, "generic_params", []) if hasattr(g, "name") and not g.name.startswith("'")]
    is_generic = len(type_params) > 0
    if is_generic:
        cargs = ", ".join(f"comptime {p}: type" for p in type_params)
        lines: List[str] = [f"{vis}fn {sname}({cargs}) type {{"]
        emitter_ctx.current_indent += 1
        fields_type_str = " ".join(str(f.field_type) for f in struct.fields)
        for p in type_params:
            if not re.search(r"\b" + re.escape(p) + r"\b", fields_type_str):
                lines.append(f"{emitter_ctx._indent()}_ = {p};")
        lines.append(f"{emitter_ctx._indent()}return struct {{")
    else:
        lines = [f"{vis}const {sname} = struct {{"]

    emitter_ctx.current_indent += 1
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
        lines.append(f"{emitter_ctx._indent()}{fname}: {ftype},")

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
        method_str = emitter_ctx._emit_function(method, parent_struct_name=sname, field_names=field_names)
        for mline in method_str.splitlines():
            lines.append(f"{emitter_ctx._indent()}{mline}")
        lines.append("")

    emitter_ctx.current_indent -= 1
    lines.append(f"{emitter_ctx._indent()}}};")
    if is_generic:
        emitter_ctx.current_indent -= 1
        lines.append("}")
    return "\n".join(lines)


def emit_function_decl(fn: FnDecl, emitter_ctx: Any, parent_struct_name: Optional[str] = None, field_names: Optional[Set[str]] = None) -> str:
    """Emit Zig function or method definition."""
    emitter_ctx.current_fn_param_names = {p.name for p in fn.params}
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
    params_str = emit_params_decl(all_params, parent_struct_name, field_names)

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

    emitter_ctx.current_indent += 1
    if fn.body:
        body_lines = emitter_ctx._emit_block_lines(fn.body)
        body_text = "\n".join(body_lines)
        discard_lines: List[str] = []
        for p_idx, p in enumerate(fn.params):
            if p.is_self:
                if not re.search(r"\bself\b", body_text):
                    discard_lines.append(f"{emitter_ctx._indent()}_ = self;")
            else:
                raw_name = p.name or ""
                clean_param_name = raw_name.replace("mut ", "").strip()
                if field_names and clean_param_name in field_names:
                    discard_lines.append(f"{emitter_ctx._indent()}const {clean_param_name} = {clean_param_name}_param;")
                    if not re.search(r"\b" + re.escape(clean_param_name) + r"\b", body_text):
                        discard_lines.append(f"{emitter_ctx._indent()}_ = {clean_param_name};")
                elif raw_name.startswith("mut "):
                    real_name = raw_name[4:].strip()
                    discard_lines.append(f"{emitter_ctx._indent()}var {real_name}_var = p{p_idx}; _ = {real_name}_var;")
                elif raw_name.startswith("[") and raw_name.endswith("]"):
                    elems = [e.strip() for e in raw_name[1:-1].split(",") if e.strip()]
                    for e_idx, e in enumerate(elems):
                        discard_lines.append(f"{emitter_ctx._indent()}const {e} = p{p_idx}[{e_idx}];")
                elif raw_name.startswith("(") and raw_name.endswith(")"):
                    elems = [e.strip() for e in raw_name[1:-1].split(",") if e.strip()]
                    for e_idx, e in enumerate(elems):
                        discard_lines.append(f'{emitter_ctx._indent()}const {e} = p{p_idx}.@"{e_idx}";')
                elif raw_name and not raw_name.isidentifier() and not raw_name.startswith("comptime"):
                    discard_lines.append(f"{emitter_ctx._indent()}_ = p{p_idx};")
                elif raw_name and raw_name != "_" and p.param_type.name != "type" and "comptime" not in raw_name:
                    if not re.search(r"\b" + re.escape(raw_name) + r"\b", body_text):
                        discard_lines.append(f"{emitter_ctx._indent()}_ = {raw_name};")

        lines.extend(discard_lines)
        lines.extend(body_lines)
    emitter_ctx.current_indent -= 1

    lines.append("}")
    return "\n".join(lines)


def emit_params_decl(params: List[Param], parent_struct_name: Optional[str] = None, field_names: Optional[Set[str]] = None) -> str:
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
                if field_names and clean_name in field_names:
                    pname = f"{clean_name}_param"
                else:
                    pname = f'@"{clean_name}"' if (clean_name in ZIG_RESERVED_KEYWORDS and not clean_name.startswith("@")) else clean_name
            parts.append(f"{pname}: {ptype}")
    return ", ".join(parts)

"""
Declaration Emitter Helpers for rs2zig Backend.
"""

from typing import List, Callable
from rs2zig.ir.nodes import TraitDecl, EnumDecl
from rs2zig.lowering.stdlib_map import map_type


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

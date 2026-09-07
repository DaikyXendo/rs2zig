"""
Standard Library and Type Mapping for rs2zig.

Provides type transformations and built-in function lowering from Rust to Zig.
"""

from typing import Dict, Optional, Union
from rs2zig.ir.nodes import TypeNode

RUST_TO_ZIG_TYPES: Dict[str, str] = {
    "i8": "i8",
    "i16": "i16",
    "i32": "i32",
    "i64": "i64",
    "i128": "i128",
    "isize": "isize",
    "u8": "u8",
    "u16": "u16",
    "u32": "u32",
    "u64": "u64",
    "u128": "u128",
    "usize": "usize",
    "f32": "f32",
    "f64": "f64",
    "bool": "bool",
    "char": "u21",
    "str": "[]const u8",
    "String": "[]u8",
    "()": "void",
}


def map_type(rust_type: Union[TypeNode, str]) -> str:
    """Map a Rust TypeNode or type string into Zig target type string representation.

    Args:
        rust_type: Input Rust TypeNode or type string.

    Returns:
        Mapped Zig type string.
    """
    if isinstance(rust_type, str):
        name = rust_type.strip()
        if name.startswith("&mut "):
            return f"*{map_type(name[5:].strip())}"
        if name.startswith("&"):
            return f"*const {map_type(name[1:].strip())}"
        if "<" in name and ">" in name:
            base, gen = name.split("<", 1)
            gen = gen.rstrip(">").strip()
            gen_parts = [p.strip() for p in gen.split(",") if not p.strip().startswith("'")]
            if not gen_parts:
                return map_type(base.strip())
            mapped_gen = ", ".join(map_type(p) for p in gen_parts)
            if base.strip() in ("Option", "std::option::Option", "Receiver", "std::sync::mpsc::Receiver"):
                res = f"?{mapped_gen}"
                while res.startswith("??"):
                    res = res[1:]
                return res
            return f"{map_type(base.strip())}({mapped_gen})"
        return RUST_TO_ZIG_TYPES.get(name, name.replace("::", "."))

    name = rust_type.name.strip()
    if name.startswith("&mut "):
        rust_type.name = name[5:].strip()
        rust_type.is_reference = True
        rust_type.is_mutable = True
        name = rust_type.name
    elif name.startswith("&"):
        rust_type.name = name[1:].strip()
        rust_type.is_reference = True
        rust_type.is_mutable = False
        name = rust_type.name
    if "<" in name and ">" in name:
        base, gen = name.split("<", 1)
        gen = gen.rstrip(">").strip()
        gen_parts = [p.strip() for p in gen.split(",") if not p.strip().startswith("'")]
        if not gen_parts:
            return map_type(base.strip())
        mapped_gen = ", ".join(map_type(p) for p in gen_parts)
        if base.strip() in ("Option", "std::option::Option", "Receiver", "std::sync::mpsc::Receiver"):
            res = f"?{mapped_gen}"
            while res.startswith("??"):
                res = res[1:]
            return res
        return f"{map_type(base.strip())}({mapped_gen})"

    if name.startswith("["):
        return name
    zig_type_name = RUST_TO_ZIG_TYPES.get(name, name.replace("::", "."))

    if rust_type.is_reference:
        prefix = "*const " if not rust_type.is_mutable else "*"
        if name == "str":
            return "[]const u8"
        return f"{prefix}{zig_type_name}"

    if rust_type.is_slice:
        return f"[]{zig_type_name}"

    if rust_type.generic_args:
        non_lifetime_args = [arg for arg in rust_type.generic_args if not str(arg).strip().startswith("'")]
        if not non_lifetime_args:
            return zig_type_name
        args_str = ", ".join(map_type(arg) for arg in non_lifetime_args)
        if name == "Vec":
            return f"std.ArrayList({args_str})"
        if name in ("Option", "std::option::Option", "Receiver", "std::sync::mpsc::Receiver"):
            res = f"?{args_str}"
            while res.startswith("??"):
                res = res[1:]
            return res
        return f"{zig_type_name}({args_str})"

    return zig_type_name

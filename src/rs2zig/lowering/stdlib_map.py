"""
Standard Library and Type Mapping for rs2zig.

Provides type transformations and built-in function lowering from Rust to Zig.
"""

from typing import Dict, Optional
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


def map_type(rust_type: TypeNode) -> str:
    """Map a Rust TypeNode into Zig target type string representation.

    Args:
        rust_type: Input Rust TypeNode.

    Returns:
        Mapped Zig type string.
    """
    name = rust_type.name.strip()
    if name.startswith("["):
        return name
    zig_type_name = RUST_TO_ZIG_TYPES.get(name, name)

    if rust_type.is_reference:
        prefix = "*const " if not rust_type.is_mutable else "*"
        if name == "str":
            return "[]const u8"
        return f"{prefix}{zig_type_name}"

    if rust_type.is_slice:
        return f"[]{zig_type_name}"

    if rust_type.generic_args:
        args_str = ", ".join(map_type(arg) for arg in rust_type.generic_args)
        if name == "Vec":
            return f"std.ArrayList({args_str})"
        if name in ("Option", "std::option::Option"):
            return f"?{args_str}"
        return f"{zig_type_name}({args_str})"

    return zig_type_name

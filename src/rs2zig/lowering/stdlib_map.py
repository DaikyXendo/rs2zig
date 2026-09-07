"""
Standard Library and Type Mapping for rs2zig.

Provides type transformations and built-in function lowering from Rust to Zig.
"""

import re
from typing import Dict, List, Optional, Tuple, Union
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
    "alloc::string::String": "[]u8",
    "std::string::String": "[]u8",
    "core::string::String": "[]u8",
    "()": "void",
}


def _split_angle_brackets(s: str) -> Optional[Tuple[str, str, str]]:
    """Extract base type, inner generic args, and suffix from angle bracketed type string."""
    first = s.find("<")
    if first == -1:
        return None
    base = s[:first].strip()
    depth = 0
    for i in range(first, len(s)):
        if s[i] == "<":
            depth += 1
        elif s[i] == ">":
            depth -= 1
            if depth == 0:
                inner = s[first + 1 : i].strip()
                suffix = s[i + 1 :].strip()
                return base, inner, suffix
    return None


def _split_top_level_commas(s: str) -> List[str]:
    """Split comma-separated arguments respecting nested bracket depth."""
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    for char in s:
        if char in "<[(":
            depth += 1
            current.append(char)
        elif char in ">])":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts


def map_type(rust_type: Union[TypeNode, str]) -> str:
    """Map a Rust TypeNode or type string into Zig target type string representation.

    Args:
        rust_type: Input Rust TypeNode or type string.

    Returns:
        Mapped Zig type string.
    """
    if isinstance(rust_type, str):
        name = rust_type.strip()
        if "'" in name:
            name = re.sub(r"'[a-zA-Z0-9_]+\s*", "", name).strip()
        if name in RUST_TO_ZIG_TYPES:
            return RUST_TO_ZIG_TYPES[name]
        if name.startswith("&mut "):
            return f"*{map_type(name[5:].strip())}"
        if name.startswith("&"):
            return f"*const {map_type(name[1:].strip())}"
        if name.startswith("[") and name.endswith("]"):
            inner = name[1:-1].strip()
            if ";" in inner:
                elem, count = inner.split(";", 1)
                return f"[{map_type(count.strip())}]{map_type(elem.strip())}"
            return f"[]{map_type(inner)}"
        split_res = _split_angle_brackets(name)
        if split_res:
            base, gen, suffix = split_res
            gen_parts = [p.strip() for p in _split_top_level_commas(gen) if not p.strip().startswith("'")]
            mapped_gen = ", ".join(map_type(p) for p in gen_parts) if gen_parts else ""
            base_clean = base.strip()
            suffix_mapped = map_type(suffix) if suffix else ""
            if base_clean in ("Option", "std::option::Option", "alloc::option::Option", "Receiver", "std::sync::mpsc::Receiver"):
                res = f"?{mapped_gen}{suffix_mapped}"
                while res.startswith("??"):
                    res = res[1:]
                return res
            if base_clean in ("Vec", "alloc::vec::Vec", "std::vec::Vec"):
                return f"std.ArrayList({mapped_gen}){suffix_mapped}"
            if base_clean in ("Box", "alloc::boxed::Box", "std::boxed::Box"):
                return f"{mapped_gen}{suffix_mapped}"
            if mapped_gen:
                return f"{map_type(base_clean)}({mapped_gen}){suffix_mapped}"
            return f"{map_type(base_clean)}{suffix_mapped}"
        return RUST_TO_ZIG_TYPES.get(name, name.replace("::", "."))

    name = rust_type.name.strip()
    if "'" in name:
        name = re.sub(r"'[a-zA-Z0-9_]+\s*", "", name).strip()
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
    if name.startswith("[") and name.endswith("]"):
        inner = name[1:-1].strip()
        if ";" in inner:
            elem, count = inner.split(";", 1)
            return f"[{map_type(count.strip())}]{map_type(elem.strip())}"
        return f"[]{map_type(inner)}"
    split_res = _split_angle_brackets(name)
    if split_res:
        base, gen, suffix = split_res
        gen_parts = [p.strip() for p in _split_top_level_commas(gen) if not p.strip().startswith("'")]
        mapped_gen = ", ".join(map_type(p) for p in gen_parts) if gen_parts else ""
        base_clean = base.strip()
        suffix_mapped = map_type(suffix) if suffix else ""
        if base_clean in ("Option", "std::option::Option", "alloc::option::Option", "Receiver", "std::sync::mpsc::Receiver"):
            res = f"?{mapped_gen}{suffix_mapped}"
            while res.startswith("??"):
                res = res[1:]
            return res
        if base_clean in ("Vec", "alloc::vec::Vec", "std::vec::Vec"):
            return f"std.ArrayList({mapped_gen}){suffix_mapped}"
        if base_clean in ("Box", "alloc::boxed::Box", "std::boxed::Box"):
            return f"{mapped_gen}{suffix_mapped}"
        if mapped_gen:
            return f"{map_type(base_clean)}({mapped_gen}){suffix_mapped}"
        return f"{map_type(base_clean)}{suffix_mapped}"

    if name.startswith("[") and name.endswith("]"):
        inner = name[1:-1].strip()
        return f"[]{map_type(inner)}"
    zig_type_name = RUST_TO_ZIG_TYPES.get(name, name.replace("::", "."))

    if rust_type.is_reference:
        prefix = "*const " if not rust_type.is_mutable else "*"
        if name in ("str", "alloc::string::String", "std::string::String"):
            return "[]const u8"
        return f"{prefix}{zig_type_name}"

    if rust_type.is_slice:
        return f"[]{zig_type_name}"

    if rust_type.generic_args:
        non_lifetime_args = [arg for arg in rust_type.generic_args if not str(arg).strip().startswith("'")]
        if not non_lifetime_args:
            return zig_type_name
        args_str = ", ".join(map_type(arg) for arg in non_lifetime_args)
        if name in ("Box", "alloc::boxed::Box", "std::boxed::Box"):
            return args_str
        if name in ("Vec", "alloc::vec::Vec", "std::vec::Vec"):
            return f"std.ArrayList({args_str})"
        if name in ("Option", "std::option::Option", "alloc::option::Option", "Receiver", "std::sync::mpsc::Receiver"):
            res = f"?{args_str}"
            while res.startswith("??"):
                res = res[1:]
            return res
        return f"{zig_type_name}({args_str})"

    return zig_type_name

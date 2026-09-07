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
    "Option": "?anytype",
    "std::option::Option": "?anytype",
    "alloc::option::Option": "?anytype",
    "__u8": "u8",
    "__u16": "u16",
    "__u32": "u32",
    "__u64": "u64",
    "__s8": "i8",
    "__s16": "i16",
    "__s32": "i32",
    "__s64": "i64",
    "AtomicBool": "std.atomic.Value(bool)",
    "AtomicU8": "std.atomic.Value(u8)",
    "AtomicU16": "std.atomic.Value(u16)",
    "AtomicU32": "std.atomic.Value(u32)",
    "AtomicU64": "std.atomic.Value(u64)",
    "AtomicUsize": "std.atomic.Value(usize)",
    "AtomicI8": "std.atomic.Value(i8)",
    "AtomicI16": "std.atomic.Value(i16)",
    "AtomicI32": "std.atomic.Value(i32)",
    "AtomicI64": "std.atomic.Value(i64)",
    "AtomicIsize": "std.atomic.Value(isize)",
    "core::sync::atomic::AtomicBool": "std.atomic.Value(bool)",
    "core::sync::atomic::AtomicUsize": "std.atomic.Value(usize)",
    "core::sync::atomic::AtomicU32": "std.atomic.Value(u32)",
    "core::sync::atomic::AtomicI32": "std.atomic.Value(i32)",
    "core::sync::atomic::AtomicU64": "std.atomic.Value(u64)",
    "core::sync::atomic::AtomicI64": "std.atomic.Value(i64)",
    "std::sync::atomic::AtomicBool": "std.atomic.Value(bool)",
    "std::sync::atomic::AtomicUsize": "std.atomic.Value(usize)",
    "std::sync::atomic::AtomicU32": "std.atomic.Value(u32)",
    "std::sync::atomic::AtomicI32": "std.atomic.Value(i32)",
    "std::sync::atomic::AtomicU64": "std.atomic.Value(u64)",
    "std::sync::atomic::AtomicI64": "std.atomic.Value(i64)",
    "Arc": "*anyopaque",
    "std::sync::Arc": "*anyopaque",
    "alloc::sync::Arc": "*anyopaque",
    "Rc": "*anyopaque",
    "alloc::rc::Rc": "*anyopaque",
    "std::rc::Rc": "*anyopaque",
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


def map_type(rust_type: Union[TypeNode, str], is_return_type: bool = False) -> str:
    """Map a Rust TypeNode or type string into Zig target type string representation.

    Args:
        rust_type: Input Rust TypeNode or type string.
        is_return_type: Whether this type is used as a function return type.

    Returns:
        Mapped Zig type string.
    """
    if isinstance(rust_type, str):
        name = rust_type.strip()
        if "'" in name:
            name = re.sub(r"'[a-zA-Z0-9_]+\s*", "", name).strip()
        if name.startswith("fn(") or name.startswith("fn ("):
            args_and_ret = name[name.find("(")+1:]
            args_part, _, ret_part = args_and_ret.partition(")")
            clean_ret = ret_part.strip().lstrip("->").strip()
            ret_str = map_type(clean_ret, is_return_type=True) if (clean_ret and clean_ret not in ("()", "void")) else "void"
            args_list = [map_type(a.strip()) for a in _split_top_level_commas(args_part) if a.strip()]
            return f"*const fn({', '.join(args_list)}) {ret_str}"
        if name.startswith("Token![") and name.endswith("]"):
            return "Token"
        if name.startswith("dyn "):
            dyn_body = name[4:].strip()
            if "Error" in dyn_body:
                return "anyerror"
            return "anyopaque"
        if name.startswith("impl "):
            return "type" if is_return_type else "anytype"
        if name in ("PhantomData", "std::marker::PhantomData", "core::marker::PhantomData"):
            return "void"
        if name.startswith("(") and name.endswith(")"):
            inner = " ".join(name[1:-1].split())
            if not inner:
                return "void"
            if "," in inner:
                elems = [map_type(p.strip()) for p in _split_top_level_commas(inner) if p.strip()]
                fields_str = ", ".join(f'@"{idx}": {e}' for idx, e in enumerate(elems))
                return f"struct {{ {fields_str} }}"
        if name in RUST_TO_ZIG_TYPES:
            return RUST_TO_ZIG_TYPES[name]
        if name in ("&anytype", "&mut anytype", "*const anytype", "*mut anytype"):
            return "anytype"
        if name.startswith("&mut [") and name.endswith("]"):
            inner = name[6:-1].strip()
            return f"[]{map_type(inner)}"
        if name.startswith("&[") and name.endswith("]"):
            inner = name[2:-1].strip()
            return f"[]const {map_type(inner)}"
        if name.startswith("&mut "):
            target = map_type(name[5:].strip())
            return "anytype" if target == "anytype" else f"*{target}"
        if name.startswith("&"):
            target = map_type(name[1:].strip())
            return "anytype" if target == "anytype" else f"*const {target}"
        if name.startswith("*mut [") and name.endswith("]"):
            inner = name[6:-1].strip()
            return f"[]{map_type(inner)}"
        if name.startswith("*const [") and name.endswith("]"):
            inner = name[8:-1].strip()
            return f"[]const {map_type(inner)}"
        if name.startswith("*mut "):
            return f"*{map_type(name[5:].strip())}"
        if name.startswith("*const "):
            return f"*const {map_type(name[7:].strip())}"
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
            mapped_gen = ", ".join("anytype" if p == "_" else map_type(p) for p in gen_parts) if gen_parts else ""
            base_clean = base.strip()
            suffix_mapped = map_type(suffix) if suffix else ""
            if base_clean in ("PhantomData", "std::marker::PhantomData", "core::marker::PhantomData"):
                return "void"
            if base_clean in ("Option", "std::option::Option", "alloc::option::Option", "Receiver", "std::sync::mpsc::Receiver"):
                res = f"?{mapped_gen}{suffix_mapped}"
                while res.startswith("??"):
                    res = res[1:]
                return res
            if base_clean in ("Vec", "alloc::vec::Vec", "std::vec::Vec"):
                return f"std.ArrayList({mapped_gen}){suffix_mapped}"
            if base_clean in ("Box", "alloc::boxed::Box", "std::boxed::Box"):
                return f"{mapped_gen}{suffix_mapped}"
            if base_clean in ("Arc", "std::sync::Arc", "alloc::sync::Arc", "Rc", "alloc::rc::Rc", "std::rc::Rc"):
                return f"*{mapped_gen}{suffix_mapped}" if mapped_gen and mapped_gen != "anyopaque" else f"*anyopaque{suffix_mapped}"
            if base_clean in ("Result", "std::result::Result", "core::result::Result"):
                if gen_parts and len(gen_parts) == 2:
                    t_type = map_type(gen_parts[0])
                    e_type = map_type(gen_parts[1])
                    return f"{e_type}!{t_type}{suffix_mapped}"
                elif gen_parts and len(gen_parts) == 1:
                    t_type = map_type(gen_parts[0])
                    return f"anyerror!{t_type}{suffix_mapped}"
                return f"anyerror!void{suffix_mapped}"
            if mapped_gen:
                return f"{map_type(base_clean)}({mapped_gen}){suffix_mapped}"
            return f"{map_type(base_clean)}{suffix_mapped}"
        return RUST_TO_ZIG_TYPES.get(name, name.replace("::", "."))

    if isinstance(rust_type, TypeNode):
        if rust_type.generic_args:
            non_lifetime = [a for a in rust_type.generic_args if not str(getattr(a, "name", a)).strip().startswith("'")]
            if non_lifetime:
                args_str = ", ".join(map_type(a) for a in non_lifetime)
                name_str = f"{rust_type.name}<{args_str}>"
            else:
                name_str = rust_type.name
        else:
            name_str = rust_type.name

        mapped = map_type(name_str, is_return_type=is_return_type)
        if rust_type.is_slice:
            if rust_type.is_reference and not rust_type.is_mutable and not mapped.startswith("[]const "):
                elem = mapped[2:] if mapped.startswith("[]") else mapped
                return f"[]const {elem}"
            elif not (mapped.startswith("[]") or mapped.startswith("[")):
                return f"[]{mapped}"
            return mapped
        if mapped == "anytype":
            return "anytype"
        if rust_type.is_reference or rust_type.is_raw_pointer:
            if not (mapped.startswith("*") or mapped.startswith("[]")):
                prefix = "*" if rust_type.is_mutable else "*const "
                return f"{prefix}{mapped}"
        return mapped

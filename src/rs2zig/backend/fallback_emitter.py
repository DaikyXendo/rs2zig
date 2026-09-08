"""
Header and Fallback Type Generator for Zig Source Code Emitter.
"""
import re
from typing import List, Set


STD_SUBMODULES = {
    "std", "self", "super", "crate", "bevy", "bevy_ecs", "aok_core", "core", "libc",
    "mem", "io", "os", "fs", "math", "fmt", "debug", "testing", "unicode", "time",
    "heap", "meta", "sort", "ascii", "atomic", "process", "valgrind", "zig"
}

STD_TYPES = {
    "std", "anytype", "void", "bool", "usize", "isize", "i8", "i16", "i32", "i64", "i128",
    "u8", "u16", "u32", "u64", "u128", "f32", "f64", "anyerror", "type", "String", "IpAddr",
    "UdpSocket", "Token", "f16", "f80", "f128"
}


def generate_fallback_headers(
    clean_body: str,
    all_declared_names: Set[str],
    imported_modules: Set[str],
    header_lines: List[str]
) -> None:
    """Generate clean fallback declarations for undeclared modules and types in header_lines.

    Args:
        clean_body: Cleaned body code string.
        all_declared_names: Set of all symbols declared in current file.
        imported_modules: Set of imported module identifiers.
        header_lines: List of header code lines to append to.
    """
    if re.search(r"\bc_void\b", clean_body) and "c_void" not in all_declared_names and not any("c_void" in h for h in header_lines):
        header_lines.append("pub const c_void = anyopaque;")
    if (re.search(r"\bcore\b", clean_body) or "core" in imported_modules) and "core" not in all_declared_names and not any("const core" in h for h in header_lines):
        header_lines.append("pub const core = std;")
    if (re.search(r"\blibc\b", clean_body) or "libc" in imported_modules) and "libc" not in all_declared_names and not any("const libc" in h for h in header_lines):
        header_lines.append("pub const libc = std.c;")

    for mod_prefix in sorted(set(re.findall(r"\b([a-z_][a-zA-Z0-9_]*)\.[A-Z]", clean_body))):
        if (
            mod_prefix not in all_declared_names
            and mod_prefix not in imported_modules
            and mod_prefix not in STD_SUBMODULES
            and not any(f"const {mod_prefix}" in h for h in header_lines)
        ):
            header_lines.append(f"pub const {mod_prefix} = *anyopaque;")

    found_types = set(re.findall(r"(?::|->|!|\*const|\?|\[|\(|\,)\s*([A-Z][a-zA-Z0-9_]{1,})\b", clean_body))
    found_types.update(re.findall(r"\b([A-Z][a-zA-Z0-9_]{1,})\s*!", clean_body))
    found_types.update(re.findall(r"\]\s*([A-Z][a-zA-Z0-9_]{1,})\b", clean_body))

    for ext_type in sorted(found_types):
        if (
            len(ext_type) > 1
            and ext_type not in all_declared_names
            and ext_type not in STD_TYPES
            and ext_type not in imported_modules
        ):
            if not re.search(r"\.\s*" + re.escape(ext_type) + r"\b", clean_body):
                header_lines.append(f"pub const {ext_type} = type;")

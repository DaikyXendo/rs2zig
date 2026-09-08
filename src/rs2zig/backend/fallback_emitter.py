"""
Header and Fallback Type Generator for Zig Source Code Emitter.
"""
import re
from typing import Set, List
from rs2zig.backend.emitter_constants import ZIG_KEYWORDS_AND_PRIMITIVES


STD_SUBMODULES = {
    "std", "self", "super", "crate", "bevy", "bevy_ecs", "aok_core", "core", "libc",
    "mem", "io", "os", "fs", "math", "fmt", "debug", "testing", "unicode", "time",
    "heap", "meta", "sort", "ascii", "atomic", "process", "valgrind", "zig"
}

STD_TYPES = {
    "std", "anytype", "void", "bool", "usize", "isize", "i8", "i16", "i32", "i64", "i128",
    "u8", "u16", "u32", "u64", "u128", "f16", "f32", "f64", "f80", "f128", "anyerror", "anyopaque", "type"
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
    if (re.search(r"\bio\b", clean_body) or "io" in imported_modules) and "io" not in all_declared_names and not any("const io" in h for h in header_lines):
        header_lines.append("pub const io = std.io;")
    if re.search(r"\brng\b", clean_body) and "rng" not in all_declared_names and not any("const rng" in h for h in header_lines):
        header_lines.append("pub const rng = type;")

    for mod_prefix in sorted(set(re.findall(r"\b([a-z_][a-zA-Z0-9_]*)\.[A-Z]", clean_body))):
        if (
            mod_prefix not in all_declared_names
            and mod_prefix not in imported_modules
            and mod_prefix not in STD_SUBMODULES
            and not any(f"const {mod_prefix}" in h for h in header_lines)
            and not any(f'const @"{mod_prefix}"' in h for h in header_lines)
        ):
            clean_mod_prefix = f'@"{mod_prefix}"' if mod_prefix in ZIG_KEYWORDS_AND_PRIMITIVES else mod_prefix
            header_lines.append(f"pub const {clean_mod_prefix} = *anyopaque;")

    clean_body_no_ats = re.sub(r"@[a-zA-Z0-9_]+", "", clean_body)

    found_types = set(re.findall(r"\b(_?[A-Z][a-zA-Z0-9_]*)\b", clean_body_no_ats))
    found_types.update(re.findall(r"\b(_bindgen_[a-zA-Z0-9_]*)\b", clean_body_no_ats))

    for ext_type in sorted(found_types):
        if (
            len(ext_type) >= 1
            and ext_type not in all_declared_names
            and ext_type not in STD_TYPES
            and ext_type not in imported_modules
            and not re.search(r"\b(?:pub\s+)?(?:const|var|fn|struct|enum|union|comptime)\s+" + re.escape(ext_type) + r"\b(?:\s*=|[\s{:(])", clean_body_no_ats)
            and not re.search(r"\b" + re.escape(ext_type) + r"\s*:\s*type\b", clean_body_no_ats)
        ):
            if ext_type == "Self":
                if not any("const Self" in h for h in header_lines):
                    header_lines.append("pub const Self = @This();")
            elif not re.search(r"\.\s*" + re.escape(ext_type) + r"\b", clean_body_no_ats):
                if not any(f"const {ext_type}" in h for h in header_lines):
                    header_lines.append(f"pub const {ext_type} = type;")

    found_fns = set(re.findall(r"(?<!\.)(?<!@)(?<!\bconst\s)(?<!\bfn\s)\b([a-z_][a-zA-Z0-9_]*)\s*\(", clean_body_no_ats))
    for fn_name in sorted(found_fns):
        if (
            fn_name not in all_declared_names
            and fn_name not in imported_modules
            and fn_name not in STD_SUBMODULES
            and fn_name not in ZIG_KEYWORDS_AND_PRIMITIVES
            and fn_name not in ("if", "while", "for", "switch", "return", "try", "catch", "defer", "errdefer", "asm", "comptime")
            and not any(f"const {fn_name}" in h for h in header_lines)
            and not any(f"fn {fn_name}" in h for h in header_lines)
            and not re.search(r"\b(?:pub\s+)?(?:const|var|fn|struct|enum|union)\s+" + re.escape(fn_name) + r"\b(?:\s*=|[\s{(])", clean_body_no_ats)
        ):
            header_lines.append(f"pub const {fn_name} = type;")

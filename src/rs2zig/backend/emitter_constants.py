"""
Zig Primitive Types and Reserved Keywords Constants for rs2zig Backend Emitter.
"""

import re

ZIG_PRIMITIVE_TYPES = {
    "u8", "u16", "u32", "u64", "u128", "i8", "i16", "i32", "i64", "i128",
    "usize", "isize", "f16", "f32", "f64", "f80", "f128", "bool", "void", "type", "anytype",
    "anyerror", "anyopaque",
    # C interop types
    "c_char", "c_short", "c_ushort", "c_int", "c_uint", "c_long", "c_ulong",
    "c_longlong", "c_ulonglong", "c_longdouble",
    # Built-in values
    "true", "false", "null", "undefined",
}

# Zig supports arbitrary-width integers (e.g. i256, u512). This regex detects them.
_ZIG_ARBITRARY_INT_RE = re.compile(r"^[iu]\d+$")


def is_zig_primitive(name: str) -> bool:
    """Check if a name is a Zig primitive type or builtin value.

    Handles standard primitives plus arbitrary-width integers like i256, u512.

    Args:
        name: The identifier to check.

    Returns:
        True if the name shadows a Zig primitive.
    """
    if name in ZIG_PRIMITIVE_TYPES:
        return True
    if _ZIG_ARBITRARY_INT_RE.match(name):
        return True
    return False


ZIG_RESERVED_KEYWORDS = {
    "addrspace", "align", "allowzero", "and", "anyframe", "anytype", "asm", "async",
    "await", "break", "callconv", "catch", "comptime", "const", "continue", "defer",
    "else", "enum", "errdefer", "error", "export", "extern", "fn", "for", "if",
    "inline", "linksection", "noalias", "noinline", "nosuspend", "opaque", "or",
    "packed", "pub", "resume", "return", "struct", "suspend", "switch", "test",
    "threadlocal", "try", "union", "unreachable", "usingnamespace", "var", "volatile", "while"
}

ZIG_KEYWORDS_AND_PRIMITIVES = ZIG_PRIMITIVE_TYPES | ZIG_RESERVED_KEYWORDS


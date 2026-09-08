"""
Zig Primitive Types and Reserved Keywords Constants for rs2zig Backend Emitter.
"""

ZIG_PRIMITIVE_TYPES = {
    "u8", "u16", "u32", "u64", "u128", "i8", "i16", "i32", "i64", "i128",
    "usize", "isize", "f16", "f32", "f64", "f80", "f128", "bool", "void", "type", "anytype",
    "anyerror", "anyopaque"
}

ZIG_RESERVED_KEYWORDS = {
    "addrspace", "align", "allowzero", "and", "anyframe", "anytype", "asm", "async",
    "await", "break", "callconv", "catch", "comptime", "const", "continue", "defer",
    "else", "enum", "errdefer", "error", "export", "extern", "fn", "for", "if",
    "inline", "linksection", "noalias", "noinline", "nosuspend", "opaque", "or",
    "packed", "pub", "resume", "return", "struct", "suspend", "switch", "test",
    "threadlocal", "try", "union", "unreachable", "usingnamespace", "var", "volatile", "while"
}

ZIG_KEYWORDS_AND_PRIMITIVES = ZIG_PRIMITIVE_TYPES | ZIG_RESERVED_KEYWORDS

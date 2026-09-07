"""
Zig Primitive Types and Reserved Keywords Constants for rs2zig Backend Emitter.
"""

ZIG_PRIMITIVE_TYPES = {
    "u8", "u16", "u32", "u64", "u128", "i8", "i16", "i32", "i64", "i128",
    "usize", "isize", "f32", "f64", "bool", "void", "type", "anytype"
}

ZIG_RESERVED_KEYWORDS = {
    "error", "test", "usingnamespace", "async", "await", "nosuspend",
    "resume", "suspend", "export", "extern", "inline", "noinline", "pub",
    "align", "const", "var", "struct", "enum", "union", "opaque", "comptime",
    "try", "catch", "if", "else", "switch", "while", "for", "break", "continue",
    "return", "defer", "errdefer", "unreachable", "asm", "threadlocal"
}

ZIG_KEYWORDS_AND_PRIMITIVES = ZIG_PRIMITIVE_TYPES | ZIG_RESERVED_KEYWORDS

# Rust to Zig Semantic Mapping Table

This living document details the semantic mappings between Rust language constructs and Zig equivalents implemented in **rs2zig**.

| Rust Construct | Zig Equivalent | Implementation Notes |
|---|---|---|
| `fn foo(x: i32) -> i32` | `fn foo(x: i32) i32` | Lowered directly via `zig_emitter.py` |
| `let mut x: i32 = 10;` | `var x: i32 = 10;` | `mut` -> `var`, immutable -> `const` |
| `println!("hello {}", x);` | `std.debug.print("hello {d}\n", .{x});` | Lowered via `control_flow.py` |
| `i32, u32, f64, bool` | `i32, u32, f64, bool` | Direct type mapping in `stdlib_map.py` |
| `char` | `u21` | Unicode 21-bit code point in Zig |
| `&str` / `String` | `[]const u8` / `[]u8` | Borrowed string slice vs owned slice |
| `Vec<T>` | `std.ArrayList(T)` | Requires allocator |
| `Option<T>` | `?T` | Zig optional type |
| `Result<T, E>` | `E!T` | Zig error union type |
| `struct Point { x: i32 }` | `const Point = struct { x: i32 };` | Struct declaration in Zig |
| `impl Point { fn init() }` | Struct methods inside `struct { ... }` | Methods placed directly in Zig struct |
| `if cond { ... } else { ... }` | `if (cond) { ... } else { ... }` | Parentheses added around condition |
| `while cond { ... }` | `while (cond) { ... }` | Lowered to Zig while loop |
| `loop { ... }` | `while (true) { ... }` | Lowered to infinite while loop |

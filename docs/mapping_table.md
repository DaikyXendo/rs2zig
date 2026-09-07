# Rust to Zig Semantic Mapping Table

This living document details the semantic mappings between Rust language constructs and Zig equivalents implemented in **rs2zig**.

| Rust Construct | Zig Equivalent | Implementation Notes |
|---|---|---|
| `fn foo(x: i32) -> i32` | `fn foo(x: i32) i32` | Lowered directly via `zig_emitter.py` |
| `fn identity<T>(x: T)` | `fn identity(comptime T: type, x: T)` | Lowered via `trait_lowering.py` |
| `let mut x: i32 = 10;` | `var x: i32 = 10;` | `mut` -> `var`, immutable -> `const` |
| `println!("hello {}", x);` | `std.debug.print("hello {d}\n", .{x});` | Lowered via `control_flow.py` |
| `i32, u32, f64, bool` | `i32, u32, f64, bool` | Direct type mapping in `stdlib_map.py` |
| `char` | `u21` | Unicode 21-bit code point in Zig |
| `&str` / `String` | `[]const u8` / `[]u8` | Borrowed string slice vs owned slice |
| `Vec<T>` | `std.ArrayList(T)` | Lowered via `ownership_pass.py` (`.empty`, `append`) |
| `Option<T>` | `?T` | Lowered to Zig optional type, `.unwrap()` -> `(opt orelse unreachable)` |
| `Result<T, E>` | `E!T` | Zig error union type, `?` -> `try` |
| `struct Point { x: i32 }` | `const Point = struct { x: i32 };` | Struct declaration in Zig |
| `impl Point { fn init() }` | Struct methods inside `struct { ... }` | Methods placed directly in Zig struct |
| `trait Speaker { fn speak(&self); }` | Interface pattern & `comptime` duck-typing | Methods attached to target struct |
| `enum Shape { Circle, Square }` | `const Shape = enum { Circle, Square };` | Simple enum in Zig |
| `enum Message { Move { x: i32 } }` | `const Message = union(enum) { Move: struct { x: i32 } };` | Tagged union in Zig |
| `match s { Shape::Circle => ... }` | `switch (s) { .Circle => ... }` | Switch pattern matching |
| `if cond { ... } else { ... }` | `if (cond) { ... } else { ... }` | Conditionals |
| `while cond { ... }` | `while (cond) { ... }` | Loops |
| `App::new().add_systems(...)` | `bevy_ecs.App.init(...).add_system(...)` | Mapped to native Zig ECS runtime |

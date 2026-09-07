# RS2ZIG Feature Support Matrix

Tracks the implementation and verification status of Rust language features in the **rs2zig** transpiler.

| Feature Category | Rust Language Feature | Status | Golden Test Case | Notes |
|---|---|---|---|---|
| Basic Functions | `fn name(params) -> RetType` | Supported | `01_hello_world` | Functions and return types |
| Primitive Types | Integer, Float, Bool, Char | Supported | `02_primitives_math` | `i32, u32, f64, bool, char` |
| Variable Bindings | `let` / `let mut` | Supported | `02_primitives_math` | Maps to `const` / `var` |
| Control Flow | `if / else`, `while`, `loop` | Supported | `02_primitives_math` | Conditionals & iteration |
| Structs & Impls | `struct` & `impl` methods | Supported | `03_struct_method` | Struct definition and methods |
| Macro Calls | `println!`, `print!` | Supported | `01_hello_world` | Lowered to `std.debug.print` |
| Standard Collections | `Vec<T>`, `String` | Phase 2 | Planned | Allocator model |
| Enums & Matching | `enum`, `Option`, `Result`, `match` | Phase 3 | Planned | Tagged unions |
| Trait & Generics | `trait`, `impl Trait`, generics | Phase 4 | Planned | Comptime interfaces |
| Proc Macros | `#[derive(...)]` macro expand | Phase 5 | Planned | Cargo expand integration |

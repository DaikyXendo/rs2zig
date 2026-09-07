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
| Standard Collections | `Vec<T>`, `String` | Supported | `04_vec_string_allocator` | Allocator model & `std.ArrayList` |
| Enums & Matching | `enum`, `union(enum)`, `match` | Supported | `05_enum_tagged_union` | Tagged unions & switch |
| Option, Result, Try | `Option`, `Result`, `?`, `unwrap` | Supported | `06_option_result_try` | Optionals & error unions |
| Generics | Generic functions `<T>` | Supported | `07_generics_comptime` | Zig `comptime T: type` |
| Traits & Impls | `trait` & `impl Trait for Struct` | Supported | `08_trait_impl` | Comptime duck-typing |
| Bevy ECS Framework | `App::new().add_systems(...).run()` | Supported | `09_bevy_ecs_minimal` | Native Zig ECS runtime |

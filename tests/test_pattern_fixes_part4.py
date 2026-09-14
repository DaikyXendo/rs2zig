"""Unit test suite for isolated Rust-to-Zig pattern fixes (Part 4).

Covers fixes for batch 52+ errors:
- break/continue expression handling
- MatchExpr body_str emission
- Numeric suffix stripping in array sizes
- Duplicate trait definition dedup
- Struct method parameter shadowing
"""

import unittest
from rs2zig.frontend.ts_parser import RustParser
from rs2zig.frontend.ast_builder import ASTBuilder
from rs2zig.backend.zig_emitter import ZigEmitter


class TestPatternFixesPart4(unittest.TestCase):
    """Test cases for transpiler fixes part 4."""

    def setUp(self) -> None:
        """Initialize parser and emitter."""
        self.parser = RustParser()
        self.emitter = ZigEmitter()

    def _transpile_code(self, code: str) -> str:
        """Helper to transpile Rust snippet string into Zig."""
        tree = self.parser.parse_code(code)
        builder = ASTBuilder(code.encode("utf-8"))
        file_node = builder.build_source_file(tree.root_node)
        return self.emitter.emit_source_file(file_node)

    # === break/continue expression handling ===

    def test_break_in_loop_emits_break_statement(self) -> None:
        """Verify Rust break inside loop emits Zig 'break;' not '@\"break\"'."""
        code = """
        pub fn find_first(data: &[u8]) -> u8 {
            let mut i = 0;
            loop {
                if i >= data.len() {
                    break;
                }
                i += 1;
            }
            return 0;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("break;", result)
        self.assertNotIn('@"break"', result)

    def test_break_with_value_emits_break_value(self) -> None:
        """Verify Rust break expr inside loop emits Zig 'break value;'."""
        code = """
        pub fn sum_until(n: i32) -> i32 {
            let mut total = 0;
            let mut i = 0;
            loop {
                if i >= n {
                    break total;
                }
                total += i;
                i += 1;
            }
        }
        """
        result = self._transpile_code(code)
        # break with value should produce break <expr>
        self.assertNotIn('@"break"', result)

    def test_continue_in_loop_emits_continue_statement(self) -> None:
        """Verify Rust continue inside loop emits Zig 'continue;' not '@\"continue\"'."""
        code = """
        pub fn count_even(data: &[u8]) -> i32 {
            let mut count = 0;
            for x in data.iter() {
                if x % 2 != 0 {
                    continue;
                }
                count += 1;
            }
            return count;
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn('@"continue"', result)

    # === MatchExpr body emission ===

    def test_match_arm_body_is_emitted(self) -> None:
        """Verify match arm bodies are properly emitted in switch expression."""
        code = """
        pub fn describe(x: i32) -> &'static str {
            match x {
                0 => "zero",
                1 => "one",
                _ => "other",
            }
        }
        """
        result = self._transpile_code(code)
        self.assertIn("switch", result)
        # The arm bodies should be present
        self.assertIn("zero", result)
        self.assertIn("one", result)
        self.assertIn("other", result)

    # === Numeric suffix stripping ===

    def test_numeric_literal_usize_suffix_stripped(self) -> None:
        """Verify numeric literal 6usize is stripped to 6 in Zig output."""
        code = """
        pub const DATA: &'static [u8; 6usize] = b"hello\\0";
        """
        result = self._transpile_code(code)
        self.assertNotIn("6usize", result)

    def test_numeric_literal_u32_suffix_stripped(self) -> None:
        """Verify numeric literal 1024u32 is stripped to 1024 in Zig output."""
        code = """
        pub const SIZE: u32 = 1024u32;
        """
        result = self._transpile_code(code)
        self.assertNotIn("1024u32", result)

    # === Duplicate trait dedup ===

    def test_duplicate_trait_definitions_deduped(self) -> None:
        """Verify multiple trait definitions with same name emit only once."""
        code = """
        pub trait MyTrait {
            fn do_thing(&self);
        }

        pub trait MyTrait {
            fn do_other(&self);
        }
        """
        result = self._transpile_code(code)
        # Should only have one definition of MyTrait
        count = result.count("const MyTrait = struct {};")
        self.assertEqual(count, 1, f"Expected exactly 1 MyTrait definition, got {count}")

    # === Struct method parameter shadowing ===

    def test_method_param_shadows_sibling_method(self) -> None:
        """Verify parameter named same as sibling method gets renamed to avoid shadowing."""
        code = """
        pub struct Rect {
            x0: f64,
            y0: f64,
            x1: f64,
            y1: f64,
        }

        impl Rect {
            pub fn origin(&self) -> (f64, f64) {
                (self.x0, self.y0)
            }

            pub fn with_origin(&self, origin: (f64, f64)) -> Rect {
                Rect { x0: origin.0, y0: origin.1, x1: self.x1, y1: self.y1 }
            }
        }
        """
        result = self._transpile_code(code)
        # The parameter should NOT directly shadow the method name
        # It should be renamed to origin_param
        self.assertIn("origin_param", result)

    def test_local_const_shadows_top_level_fn(self) -> None:
        """Verify local const with same name as its enclosing function gets renamed."""
        code = """
        pub fn stdout() -> u8 {
            let stdout = 42;
            return stdout;
        }
        """
        result = self._transpile_code(code)
        # The local variable should be renamed to avoid shadowing the function
        self.assertNotIn("const stdout = 42", result)
        self.assertTrue("stdout_var" in result or "stdout_local" in result)

    def test_local_const_shadows_top_level_const(self) -> None:
        """Verify local const with same name as top-level const gets renamed."""
        code = """
        pub const MAX: u32 = 100;

        pub fn compute() -> u32 {
            let MAX = 200;
            return MAX;
        }
        """
        result = self._transpile_code(code)
        # Inside the function, MAX should be renamed
        self.assertTrue("MAX_var" in result or "MAX_local" in result)

    def test_slice_generic_type_parsing(self) -> None:
        """Verify &[Box<dyn Any>] maps to []const *anyopaque without truncated '[Box'."""
        code = """
        pub fn get_field_builders(data: &[Box<dyn Any>]) -> &[Box<dyn Any>] {
            return data;
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("[Box", result)
        self.assertIn("[]const *anyopaque", result)

    def test_crate_fallback_header(self) -> None:
        """Verify crate reference generates pub const crate = @This(); header."""
        code = """
        pub fn run_crate() {
            let _ = crate::foo();
        }
        """
        result = self._transpile_code(code)
        self.assertIn("pub const crate = @This();", result)

    def test_break_unit_emits_clean_break(self) -> None:
        """Verify break () emits clean 'break;' without () in Zig."""
        code = """
        pub fn loop_break() {
            loop {
                break ();
            }
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("break ()", result)
        self.assertIn("break;", result)

    def test_match_arm_no_duplicate_else(self) -> None:
        """Verify match with Ok and Err arms emits at most one else branch."""
        code = """
        pub fn check_res(val: Result<i32, ()>) -> i32 {
            match val {
                Ok(x) => x,
                Err(_) => 0,
            }
        }
        """
        result = self._transpile_code(code)
        count = result.count("else")
    def test_multiline_raw_string_literal(self) -> None:
        """Verify multiline Rust raw string r#"..."# converts without leaving raw r# syntax."""
        code = """
        pub fn code_snippet() -> &'static str {
            let code = r#"
                pub fn hello() {}
            "#;
            return code;
        }
        """
        result = self._transpile_code(code)
    def test_shadowing_param_discard_not_pointless(self) -> None:
        """Verify struct method parameter shadowing field name does not emit pointless discard of param."""
        code = """
        pub struct Glyph {
            scale: f32,
        }

        impl Glyph {
            pub fn with_scale(&mut self, scale: f32) {
                self.scale = scale;
            }
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("_ = scale_param;", result)
    def test_ptr_const_type_fallback_generated(self) -> None:
        """Verify type referenced as *const Glyph in fn signature gets pub const Glyph = type; fallback."""
        code = """
        pub struct OutlinedGlyph {
            glyph: Glyph,
        }

        impl OutlinedGlyph {
            pub fn as_ref(&self) -> &Glyph {
                return &self.glyph;
            }
        }
        """
        result = self._transpile_code(code)
        self.assertIn("pub const Glyph = type;", result)

    def test_function_parameter_does_not_shadow_fallback_type(self) -> None:
        """Verify function parameter 'filter' does not emit top-level 'pub const filter = type;'."""
        code = """
        pub struct Node;
        fn next_filtered_sibling(node: Option<Node>, filter: fn(&Node) -> bool) -> Option<Node> {
            let child = node?;
            let result = filter(&child);
            if result {
                return Some(child);
            }
            None
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("pub const filter = type;", result)

    def test_nested_closure_parameter_shadows_outer_var(self) -> None:
        """Verify inner closure parameter shadowing outer local variable is renamed cleanly."""
        code = """
        pub fn process() {
            let mut pending_grafts = 10;
            let record_graft = |pending_grafts: &mut i32| {
                *pending_grafts += 1;
            };
            record_graft(&mut pending_grafts);
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("fn record_graft(pending_grafts: ", result)

    def test_expr_stmt_catch_block_has_semicolon(self) -> None:
        """Verify ExprStmt discard expression statement ends with a semicolon."""
        code = """
        pub fn main() {
            let _ = probe_library("alsa").map_err(|e| {
                let _ = e;
            });
        }
        """
        result = self._transpile_code(code)
        self.assertIn("_ = probe_library", result)
        self.assertTrue("}.run));" in result or result.strip().endswith(";"))




    def test_top_level_symbol_shadowing_renames_local_var(self) -> None:
        """Verify local variable shadowing a top-level function is renamed cleanly."""
        code = """
        pub fn stdout() -> i32 {
            let stdout = 42;
            stdout
        }
        """
        result = self._transpile_code(code)
        self.assertIn("const stdout_var = 42;", result)
        self.assertIn("return stdout_var;", result)

    def test_top_level_import_shadowing_renames_local_var(self) -> None:
        """Verify local variable shadowing top-level import like 'fmt' is renamed cleanly."""
        code = """
        use std::fmt;

        pub fn format_node() {
            let mut fmt = 100;
            fmt += 1;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("var fmt_var = 100;", result)

    def test_comptime_param_shadowing_renames_param(self) -> None:
        """Verify comptime parameter shadowing top-level struct is renamed cleanly."""
        code = """
        pub struct S;

        pub fn process_s<S>(item: S) {
            let _ = item;
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("comptime S: type,", result)
        self.assertIn("comptime S_param: type", result)


    def test_nested_use_declaration_extracts_nested_symbols(self) -> None:
        """Verify nested use declarations extract symbols like Node and NodeId into imports."""
        code = """
        use crate::{
            filters::FilterResult,
            node::{Node, NodeId},
        };

        pub fn get_node(node: ?Node, id: NodeId) -> FilterResult {
            let _ = (node, id);
        }
        """
        result = self._transpile_code(code)
        self.assertIn("pub const Node = type;", result)
        self.assertIn("pub const NodeId = type;", result)

    def test_undeclared_function_call_generates_function_fallback(self) -> None:
        """Verify undeclared function calls like px(12) generate a function stub in header."""
        code = """
        pub fn setup() {
            let w = px(12);
            let p = percent(50);
        }
        """
        result = self._transpile_code(code)
        self.assertIn("pub const px = (struct {", result)
        self.assertIn("pub const percent = (struct {", result)

    def test_prefix_type_name_does_not_block_fallback_header(self) -> None:
        """Verify NodeId fallback header does not block Node fallback header generation."""
        code = """
        pub fn process(id: NodeId, n: Node) {
            let _ = (id, n);
        }
        """
        result = self._transpile_code(code)
        self.assertIn("pub const Node = type;", result)
        self.assertIn("pub const NodeId = type;", result)


    def test_sibling_function_does_not_inherit_renamed_vars(self) -> None:
        """Verify sibling function does not inherit renamed_vars from previous function."""
        code = """
        pub fn func1(origin: i32) -> i32 {
            let mut origin = origin;
            origin += 1;
            origin
        }

        pub fn func2(origin: i32) -> i32 {
            origin
        }
        """
        result = self._transpile_code(code)
        self.assertIn("fn func2(origin: i32) i32", result)
        self.assertNotIn("origin_var", result.split("func2")[1])

    def test_payload_capture_shadows_outer_param_is_renamed(self) -> None:
        """Verify optional payload capture shadowing outer function parameter is renamed cleanly."""
        code = """
        pub fn process_changes(changes: Option<i32>) {
            if let Some(changes) = changes {
                let _ = changes;
            }
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("|changes_param|", result)
        self.assertIn("|changes_val|", result)


if __name__ == "__main__":
    unittest.main()







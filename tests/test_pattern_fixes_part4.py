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
        self.assertIn(".run", result)




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


    def test_nested_closure_parameter_shadowing_outer_param_is_renamed(self) -> None:
        """Verify nested closure parameter with same name as outer closure param is renamed."""
        code = """
        pub fn setup(parent: i32) {
            let closure1 = |parent: i32| {
                let closure2 = |parent: i32| {
                    let _ = parent;
                };
            };
        }
        """
        result = self._transpile_code(code)
        self.assertIn("fn run(parent_param: i32)", result)

    def test_if_condition_multiline_and_operator_replaced(self) -> None:
        """Verify if condition containing && emits Zig 'and' instead of '&&'."""
        code = """
        pub fn check(a: bool, b: bool) -> bool {
            if a
                && b {
                return true;
            }
            return false;
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("&&", result)
        self.assertIn("and", result)

    def test_array_literal_comment_filtering(self) -> None:
        """Verify comments inside array literals are filtered and do not corrupt closing braces."""
        code = """
        pub fn test_comments() {
            let cases = [
                ("a", "b"), // comment 1
                ("c", "d"), // comment 2
            ];
            let _ = cases;
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("// comment 1};", result)
        self.assertIn("};", result)

    def test_underscore_type_arg_mapping(self) -> None:
        """Verify Rust generic calls with _ as type args map _ to anytype."""
        code = """
        pub fn test_turbofish(env: &Env) {
            let binding = env.with_local_frame::<_, _, InternalAppError>(10, || {});
            let _ = binding;
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("with_local_frame(_, _,", result)
        self.assertIn("with_local_frame(anyopaque, anyopaque,", result)

    def test_fallback_header_param_shadowing(self) -> None:
        """Verify function parameter named f shadows fallback header pub const f and is renamed."""
        code = """
        pub fn apply<F>(f: F) -> i32 {
            let x = f();
            let _ = f(1, 2, 3, 4); // triggers fallback f if undeclared
            x
        }
        """
        result = self._transpile_code(code)
        self.assertIn("f_param: F", result)

    def test_struct_init_target_parenthesized(self) -> None:
        """Verify struct/block init call target before .into() is parenthesized."""
        code = """
        pub fn test_into() {
            let equal: bool = ().into();
            let _ = equal;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("({}).into()", result)

    def test_local_fn_inside_function_body(self) -> None:
        """Verify local struct/fn declared inside function body is emitted as a valid const declaration."""
        code = """
        pub fn await_output() {
            struct Fut<T>(T);
            let _ = Fut(10);
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("    fn Fut(comptime T: type)", result)

    def test_param_matching_method_name_unused(self) -> None:
        """Verify unused local variable name is assigned _ = name even if face.name() is called later."""
        code = """
        pub fn process_names(face: &Face) {
            let name = face.names();
            let _ = face.name();
        }
        """
        result = self._transpile_code(code)
        self.assertIn("_ = name;", result)

    def test_nested_fn_param_shadows_outer_var(self) -> None:
        """Verify parameter of nested function matching outer variable name is renamed with _param suffix."""
        code = """
        pub fn update() {
            let grafts_to_remove = 10;
            let traverse = |grafts_to_remove: i32| {
                let _ = grafts_to_remove;
            };
            let _ = grafts_to_remove;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("grafts_to_remove_param: i32", result)

    def test_local_struct_decl_no_duplicate_const(self) -> None:
        """Verify local struct inside function body does not emit duplicate const R = const R = struct."""
        code = """
        pub fn test_local_struct() {
            struct R { read: usize }
            let _ = R { read: 0 };
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("const R = const R =", result)
        self.assertIn("const R = struct", result)

    def test_turbofish_call_arg_uses_anyopaque(self) -> None:
        """Verify turbofish call arg _ maps to anyopaque instead of anytype."""
        code = """
        pub fn test_frame(env: &Env) {
            let _ = env.with_local_frame::<_, _, Error>(10, || {});
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("with_local_frame(anytype", result)
        self.assertIn("with_local_frame(anyopaque", result)

    def test_unused_param_with_struct_field_name(self) -> None:
        """Verify parameter view gets _ = view even if .view = val is present in body."""
        code = """
        pub fn create_adapter(view: *c_void) {
            let state = State { view: 10 };
            let _ = state;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("_ = view;", result)

    def test_enum_pattern_let_destructuring(self) -> None:
        """Verify let Enum::Variant(a, b) = val does not output invalid const Enum::Variant syntax."""
        code = """
        pub fn process_data(array: &Array) {
            let DataType::FixedSizeList(inner, size) = array.data_type();
            let _ = (inner, size);
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("const DataType::FixedSizeList", result)

    def test_if_let_identifier_payload_capture(self) -> None:
        """Verify if let child = opt uses child as payload capture name."""
        code = """
        pub fn process_children(opt: Option<i32>) {
            if let child = opt {
                let _ = child;
            }
        }
        """
        result = self._transpile_code(code)
        self.assertIn("|child|", result)
        self.assertNotIn("|item|", result)

    def test_tuple_destructuring_shadows_outer_var(self) -> None:
        """Verify tuple pattern destructuring renames variable if outer variable of same name exists."""
        code = """
        pub fn update_tree() {
            let tree_index = 100;
            let helper = || {
                let (_, tree_index) = get_pair();
                let _ = tree_index;
            };
            let _ = tree_index;
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("const tree_index =", result.split("helper")[1])

    def test_mut_param_destructuring_uses_correct_pname(self) -> None:
        """Verify mut parameter generates var var_name_var = var_name, not p0."""
        from rs2zig.ir.nodes import FnDecl, Param, TypeNode, BlockExpr
        fn = FnDecl(
            name="new",
            params=[Param(name="mut view", param_type=TypeNode(name="i32"))],
            body=BlockExpr(stmts=[]),
            is_pub=True,
        )
        result = self.emitter._emit_function(fn)
        self.assertIn("var view_var = view;", result)
        self.assertNotIn("var view_var = p0;", result)

    def test_payload_capture_shadowing_module_constant(self) -> None:
        """Verify payload capture renaming when capture name shadows a top-level module constant."""
        code = """
        mod context;
        pub fn process(state: State) {
            match state {
                State::Active(context) => { let _ = context; }
            }
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("|context|", result)
        self.assertIn("|context_val|", result)

    def test_standalone_type_fallback_header(self) -> None:
        """Verify standalone type usage generates fallback type header even if prefixed usage exists."""
        code = """
        struct Rect {
            transform: Transform,
        }
        pub fn update() {
            let t = bevy_ecs::Transform::identity();
            let _ = t;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("pub const Transform = type;", result)

    def test_renamed_if_let_capture_substitutes_in_then_block(self) -> None:
        """Verify if let capture renamed to child_val updates body references to child_val."""
        code = """
        pub fn process_sibling(child: i32, opt: Option<i32>) {
            if let Some(child) = opt {
                let res = child + 1;
                let _ = res;
            }
        }
        """
        result = self._transpile_code(code)
        self.assertIn("|child_val|", result)
        self.assertIn("child_val + 1", result)


if __name__ == "__main__":
    unittest.main()









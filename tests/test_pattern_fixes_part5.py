"""Unit test suite for isolated Rust-to-Zig pattern fixes (Part 5).

Covers fixes for batch 80+ errors:
- Sibling function scope variable isolation
- Nested payload capture renaming
- Multiline switch & struct decl discard placement
- OR pattern tuple matching
"""

import unittest
from rs2zig.frontend.ts_parser import RustParser
from rs2zig.frontend.ast_builder import ASTBuilder
from rs2zig.backend.zig_emitter import ZigEmitter


class TestPatternFixesPart5(unittest.TestCase):
    """Test cases for transpiler fixes part 5."""

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

    def test_nested_some_pattern_extracts_innermost_name(self) -> None:
        """Verify nested pattern if let Some(Some(child)) extracts child as capture name."""
        code = """
        pub fn process_nested(opt: Option<Option<i32>>) {
            if let Some(Some(child)) = opt {
                let _ = child;
            }
        }
        """
        result = self._transpile_code(code)
        self.assertIn("|child|", result)

    def test_unused_multiline_switch_constant_emits_discard(self) -> None:
        """Verify multiline switch initializer constant that is unused emits _ = var_name;."""
        code = """
        pub fn check_val(x: i32) -> i32 {
            let direction = match x {
                v => v,
            };
            return 0;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("_ = direction;", result)

    def test_renamed_variable_in_index_expression(self) -> None:
        """Verify renamed mutable variable in index access subtrees_to_remove[i] gets updated."""
        code = """
        pub fn process_list(subtrees_to_remove: i32) {
            let mut subtrees_to_remove = vec![1, 2];
            subtrees_to_remove.push(3);
            let first = subtrees_to_remove[0];
            let _ = (subtrees_to_remove_param, first);
        }
        """
        result = self._transpile_code(code)
        self.assertIn("subtrees_to_remove_var[0]", result)

    def test_match_arm_body_has_semicolon_before_block_end(self) -> None:
        """Verify match arm with payload capture adds semicolon to trailing expression before block end."""
        code = """
        pub fn get_ctx(state: State) {
            match state {
                State::Active(context) => Rc::clone(context),
            }
        }
        """
        result = self._transpile_code(code)
        self.assertIn(".Active => |context| Rc.clone(context),", result)

    def test_closure_tuple_param_destructuring(self) -> None:
        """Verify closure tuple pattern parameter (|(_, f)| ...) destructures f in body."""
        code = """
        pub fn find_item(items: &[Item]) {
            let _ = items.iter().find(|(_, f)| f.is_valid());
        }
        """
        result = self._transpile_code(code)
        self.assertIn('p0.@"1";', result)

    def test_multi_line_tuple_destructuring_does_not_emit_pointless_discard(self) -> None:
        """Verify tuple pattern destructuring used in subsequent statements does not emit pointless discard of tuple temp."""
        code = """
        pub fn process_point(position: Point) -> Rect {
            let (x_trunc, x_fract) = (position.x.trunc(), position.x.fract());
            return Rect { min: x_trunc, max: x_fract };
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("_ = __tuple_tmp", result)

    def test_unused_tuple_destructured_variable_emits_discard(self) -> None:
        """Verify tuple pattern destructuring with unused field emits discard for the unused variable."""
        code = """
        pub fn process_id(id: Id) {
            let (a, b) = id.to_components();
            let _ = a;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("_ = b;", result)

    def test_generic_comptime_param_shadowing_emits_correct_discard(self) -> None:
        """Verify generic comptime parameter renaming emits correct discard if unused or omits discard if used."""
        code = """
        pub fn assert_ser<T>(allocator: Allocator, v: &T, expected_bytes: &[u8]) {
            let mut actual_bytes = vec![];
            v.serialize(&mut actual_bytes);
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("_ = T;", result)
        self.assertIn("_ = allocator;", result)

    def test_unused_multiline_switch_constant_emits_discard_after_switch(self) -> None:
        """Verify unused variable assigned from multiline switch statement emits discard AFTER switch block ends."""
        code = """
        pub fn process_window(window: Window) {
            let view = match window {
                Window::AppKit(handle) => handle.ns_view,
                _ => 0,
            };
            return;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("};\n    _ = view;", result)
        self.assertNotIn("switch (window) {\n    _ = view;", result)

    def test_unused_unit_struct_emits_discard_after_struct_block(self) -> None:
        """Verify unused struct declaration inside function body emits discard AFTER struct definition block."""
        code = """
        pub fn test_drop() {
            struct Bump;
            return;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("};\n    _ = Bump;", result)
        self.assertNotIn("struct {\n    _ = Bump;", result)

    def test_or_pattern_tuple_matching(self) -> None:
        """Verify match arm with OR pattern tuple matching splits alternatives cleanly."""
        code = """
        pub fn check_nulls(lhs: Option<i32>, rhs: Option<i32>) -> bool {
            match (lhs, rhs) {
                (Some(_), None) | (None, Some) => true,
                _ => false,
            }
        }
        """
        result = self._transpile_code(code)
        self.assertIn(".{ .Some, .None }, .{ .None, .Some } => true,", result)


    def test_uninitialized_let_stmt_emits_var_undefined(self) -> None:
        """Verify uninitialized let statement emits var with = undefined initializer in Zig."""
        code = """
        pub fn process() {
            let error_generic_member_access;
            if true {
                error_generic_member_access = true;
            }
        }
        """
        result = self._transpile_code(code)
        self.assertIn("var error_generic_member_access = undefined;", result)
        self.assertNotIn("const error_generic_member_access;", result)

    def test_closure_tuple_param_destructuring_identifier_preservation(self) -> None:
        """Verify closure tuple pattern destructuring preserves parameter identifier without adding underscores."""
        code = """
        pub fn resolve(fields: Vec<i32>) {
            fields.iter().find(|(_, f)| f.data_type() == 0);
        }
        """
        result = self._transpile_code(code)
        self.assertIn("const f = p0.[\"1\"]", result.replace("@\"1\"", "[\"1\"]"))
        self.assertIn("f.data_type()", result)
        self.assertNotIn("_f.data_type()", result)

    def test_nested_function_param_shadowing_outer_param(self) -> None:
        """Verify nested function parameter shadowing outer function parameter gets distinct non-duplicate name."""
        code = """
        pub fn outer(parent: i32) {
            let inner = |parent: i32| {
                let _ = parent;
            };
        }
        """
        result = self._transpile_code(code)
        self.assertIn("pub fn outer(parent: i32)", result)
        self.assertIn("fn run(parent_param: i32)", result)

    def test_fallback_bevy_and_ndk_namespaces(self) -> None:
        """Verify bevy and ndk module references emit pub const bevy / ndk fallback declarations."""
        code = """
        pub const NORMAL: i32 = bevy.color.BLUE;
        pub fn setup() {
            let _ = ndk.input.event;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("pub const bevy = *anyopaque;", result)
        self.assertIn("pub const ndk = *anyopaque;", result)


    def test_multiple_shadowing_let_stmts_emit_unique_alt_names(self) -> None:
        """Verify multiple shadowing let statements generate unique dedup names without duplicate redeclarations."""
        code = """
        pub fn process_point(point: i32) {
            let point = point + 1;
            let point = point + 2;
            let point = point + 3;
            let _ = point;
        }
        """
        result = self._transpile_code(code)
        self.assertIn("point_var", result)
        self.assertIn("point_var_alt", result)
        self.assertIn("point_var_alt_alt", result)

    def test_fallback_thread_namespace(self) -> None:
        """Verify thread module references emit pub const thread fallback declaration."""
        code = """
        pub fn run_thread() {
            thread::scope(|s| { let _ = s; });
        }
        """
        result = self._transpile_code(code)
        self.assertIn("pub const thread = *anyopaque;", result)

    def test_option_anytype_mapped_to_anytype(self) -> None:
        """Verify Option<impl Trait> maps to anytype instead of invalid ?anytype in Zig."""
        code = """
        pub fn handle(handler: Option<impl Fn()>) -> Option<impl Fn()> {
            handler
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("?anytype", result)

    def test_inline_closure_expression_whitespace_flattening(self) -> None:
        """Verify inline closure inside if condition emits single line structure without breaking parent if condition."""
        code = """
        pub fn check(val: Option<i32>) {
            if val.is_some_and(|v| v > 0) {
                let _ = val;
            }
        }
        """
        result = self._transpile_code(code)
        self.assertNotIn("if (v;", result)
        self.assertIn("struct { fn run(v: anytype)", result.replace("\n", " "))

    def test_array_literal_comment_semicolon_placement(self) -> None:
        """Verify array literal constant with trailing line comment places semicolon outside comment."""
        code = """
        pub const BYTE_FREQUENCIES: [u8; 2] = [
            1,
            2 // comment
        ];
        """
        result = self._transpile_code(code)
    def test_tuple_index_in_field_access_quoted(self) -> None:
        """Verify field access with tuple index like bits.0 quotes number as @"0"."""
        code = """
        pub fn process(self: &State) {
            let x = self.bits.0;
            let _ = x;
        }
        """
        result = self._transpile_code(code)
        self.assertIn('.@"0"', result)

    def test_local_var_shadowing_struct_method_renamed(self) -> None:
        """Verify local variable matching struct method name is renamed with _var suffix."""
        code = """
        struct State;
        impl State {
            pub fn update(&mut self) {}
            pub fn process(&mut self) {
                let update = 10;
                let _ = update;
            }
        }
        """
        result = self._transpile_code(code)
        self.assertIn("update_var", result)


if __name__ == "__main__":
    unittest.main()



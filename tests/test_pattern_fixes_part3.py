"""Unit test suite for isolated Rust-to-Zig pattern fixes (Part 3)."""

import unittest
from rs2zig.frontend.ts_parser import RustParser
from rs2zig.frontend.ast_builder import ASTBuilder
from rs2zig.backend.zig_emitter import ZigEmitter


class TestPatternFixesPart3(unittest.TestCase):
    """Test cases for transpiler fixes part 3."""

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

    def test_raw_byte_string_literal_lowering(self) -> None:
        """Verify Rust raw byte string literal br"hello" lowers to Zig string literal "hello"."""
        code = """
        pub fn get_str() -> &'static str {
            let msg = br"hello";
            return msg;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn('br"hello"', zig)
        self.assertIn('"hello"', zig)

    def test_struct_pattern_destructuring_let(self) -> None:
        """Verify let Rect { min, max } = bounds; lowers to destructured variable assignments in Zig."""
        code = """
        pub fn get_bounds(bounds: Rect) {
            let Rect { min, max } = bounds;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("const Rect { min, max }", zig)
        self.assertIn("const __struct_tmp_1 = bounds;", zig)

    def test_arc_type_lowering(self) -> None:
        """Verify Arc<T> and bare Arc lower to *T and *anyopaque in Zig."""
        code = """
        pub fn process(f: Arc<Font>, g: Arc) {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("Arc(Font)", zig)
        self.assertIn("*Font", zig)
        self.assertIn("*anyopaque", zig)

    def test_result_type_lowering(self) -> None:
        """Verify Result<FontVec, InvalidFont> lowers to InvalidFont!FontVec in Zig."""
        code = """
        pub fn try_from_vec() -> Result<FontVec, InvalidFont> {
            return Ok(FontVec {});
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("Result(FontVec, InvalidFont)", zig)
        self.assertIn("InvalidFont!FontVec", zig)

    def test_nested_array_type_lowering(self) -> None:
        """Verify nested array type [[u8; 16]; 256] lowers to valid Zig 2D array [256][16]u8."""
        code = """
        pub const STATE_CHANGES: [[u8; 16]; 256] = [[0; 16]; 256];
        """
        zig = self._transpile_code(code)
        self.assertIn("STATE_CHANGES: [256][16]u8", zig)

    def test_return_unit_tuple_lowering(self) -> None:
        """Verify return () lowers to return; in Zig to avoid returning empty tuple expression ()."""
        code = """
        pub fn generate_table() {
            return ();
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("return ();", zig)
        self.assertIn("return;", zig)

    def test_standalone_semicolon_elimination(self) -> None:
        """Verify standalone bare semicolon lines ; in function bodies are eliminated."""
        code = """
        pub fn encode() {
            let x = 1;
            ;
            return x;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("    ;\n", zig)

    def test_double_dot_error_prefix_elimination(self) -> None:
        """Verify error..ComputeError does not contain double dots error.. in Zig output."""
        code = """
        pub fn compute() -> ArrowError {
            return error::ComputeError;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("error..", zig)

    def test_anytype_in_type_argument_lowering(self) -> None:
        """Verify type argument wildcard ArrayVec<_, 2> lowers to ArrayVec(anyopaque, 2) in Zig."""
        code = """
        pub fn test_slice() {
            let res: ArrayVec<_, 2> = ArrayVec::new();
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("anytype, 2", zig)
        self.assertIn("anyopaque, 2", zig)

    def test_self_identifier_fallback(self) -> None:
        """Verify Self identifier in expressions or returns emits pub const Self = @This(); fallback in Zig."""
        code = """
        pub fn from_data(data: &[u8]) -> Self {
            return Self::try_from(data);
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("pub const Self = @This();", zig)

    def test_static_method_type_fallback(self) -> None:
        """Verify static type method calls like Rasterizer::new() generate pub const Rasterizer = type; fallback."""
        code = """
        pub fn create_r() {
            let r = Rasterizer::new(6, 16);
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("pub const Rasterizer = type;", zig)

    def test_unused_closure_arg_discard_lowering(self) -> None:
        """Verify closure with unused parameter like map_err(|_| 42) emits _ = arg0; discard line in Zig wrapper."""
        code = """
        pub fn map_val(res: Result<u8, Error>) {
            let res2 = res.map_err(|_| 42);
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("_ = arg0;", zig)

    def test_method_parameter_struct_field_shadowing_fix(self) -> None:
        """Verify struct method parameter matching struct field name origin does not shadow declaration in Zig signature."""
        code = """
        pub struct Rect {
            pub origin: Point,
            pub size: Size,
        }

        impl Rect {
            pub fn from_origin_size(origin: Point, size: Size) -> Rect {
                return Rect { origin, size };
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("fn from_origin_size(origin:", zig)
        self.assertIn("fn from_origin_size(origin_param:", zig)

    def test_ffi_fn_pointer_generic_arrow_split(self) -> None:
        """Verify Option<unsafe extern "C" fn(scope: *mut snd_pcm_scope_t) -> c_int> lowers without splitting at -> arrow."""
        code = """
        pub struct Ops {
            pub enable: Option<unsafe extern "C" fn(scope: *mut snd_pcm_scope_t) -> c_int>,
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn(" -)", zig)
        self.assertIn("?*const fn(scope: *snd_pcm_scope_t) c_int", zig)

    def test_expr_stmt_leading_brace_parentheses(self) -> None:
        """Verify statement starting with empty struct or tuple like {}.into(); is wrapped in parens ({}).into();."""
        code = """
        pub fn process() {
            {}.into();
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("\n    {}.into();", zig)
        self.assertIn("({}).into();", zig)

    def test_match_enum_payload_capture_lowering(self) -> None:
        """Verify match arm with payload SearchKind::Teddy(ref teddy) lowers to .Teddy => |teddy| in Zig."""
        code = """
        pub fn search(kind: SearchKind) {
            match kind {
                SearchKind::Teddy(ref teddy) => {},
                SearchKind::RabinKarp => {},
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn(".Teddy(ref teddy)", zig)
        self.assertIn(".Teddy => |teddy|", zig)

    def test_if_let_enum_pattern_match_lowering(self) -> None:
        """Verify if let WindowEvent::Focused(is_focused) = event lowers to if (event) |is_focused| or valid Zig if payload capture."""
        code = """
        pub fn process_event(event: WindowEvent) {
            if let WindowEvent::Focused(is_focused) = event {
                do_something();
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("if (.Focused(is_focused) = event)", zig)
        self.assertIn("|is_focused|", zig)

    def test_if_expr_double_equals_comparison(self) -> None:
        """Verify if comparison with == is not split as if let assignment with leading =."""
        code = """
        pub fn check(role: Role) {
            if role == Role::GenericContainer || role == Role::TextRun {
                return;
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("if (=", zig)
        self.assertIn("role == .GenericContainer", zig)

    def test_string_literal_null_byte_escape(self) -> None:
        """Verify string literal with null byte \\0 lowers to \\x00 in Zig."""
        code = """
        pub const PREFIX: &'static str = "l\\0";
        """
        zig = self._transpile_code(code)
        self.assertNotIn('"l\\0"', zig)
        self.assertIn('"l\\x00"', zig)

    def test_tuple_match_arm_pattern(self) -> None:
        """Verify tuple match arm (State::Escape, true) lowers cleanly without bare dot . pattern."""
        code = """
        pub fn parse(state: State, more: bool) {
            match (state, more) {
                (State::Escape, true) => {},
                _ => {},
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn(" . =>", zig)

    def test_trailing_block_expr_return_unit(self) -> None:
        """Verify block ending with () emits return; instead of return ();."""
        code = """
        pub fn finish(state: &mut State, sid: usize) {
            state.at += 1;
            ()
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("return ();", zig)
        self.assertIn("return;", zig)

    def test_param_with_leading_underscore_discard(self) -> None:
        """Verify function parameter like _cmd: Sel emits _ = _cmd; discard line if unused."""
        code = """
        pub fn focus_forwarder(this: &NSWindow, _cmd: Sel) -> *mut AnyObject {
            return std::ptr::null_mut();
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("_ = _cmd;", zig)

    def test_tuple_switch_arm_pattern_syntax(self) -> None:
        """Verify tuple pattern arm (State::Ground, true) lowers to .{ .Ground, true } in Zig switch."""
        code = """
        pub fn parse(state: State, more: bool) {
            match (state, more) {
                (State::Ground, true) => {},
                _ => {},
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("(State::Ground, true) =>", zig)
        self.assertIn(".{ .Ground, true } =>", zig)

    def test_turbofish_nested_generic_partition_fix(self) -> None:
        """Verify turbofish with nested generic args collect::<Result<Vec<_>, ArrowError>>() parses without breaking at Vec<_)."""
        code = """
        pub fn process(cols: &Cols) {
            let res = cols.collect::<Result<Vec<_>, ArrowError>>();
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("Vec<_)_", zig)
        self.assertNotIn("Result<Vec<_)", zig)

    def test_match_arm_struct_pattern_rest_dots_lowering(self) -> None:
        """Verify match arm with struct pattern State::Inactive { is_view_focused, .. } lowers without invalid is_view_focused, .. inside pattern."""
        code = """
        pub fn handle(state: State) {
            match state {
                State::Inactive { is_view_focused, .. } => {},
                _ => {},
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("is_view_focused, ..", zig)

    def test_let_stmt_val_expr_leading_brace_parens(self) -> None:
        """Verify let x: bool = {}.into(); wraps initializer expression starting with brace in parens."""
        code = """
        pub fn check() {
            let x: bool = {}.into();
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("= {}.into();", zig)
        self.assertIn("= ({}).into();", zig)

    def test_call_args_comment_filtering(self) -> None:
        """Verify comments inside function call arguments do not emit // comments inline in argument list."""
        code = """
        pub fn convert(sec: u32, milli_sec: u32) -> Option<DateTime> {
            return DateTime::from_timestamp(
                // comment 1
                sec,
                // comment 2
                milli_sec,
            );
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("from_timestamp(//", zig)

    def test_dyn_trait_trailing_plus_lifetime_clean(self) -> None:
        """Verify dyn StdError + 'static lowers cleanly without trailing + inside parens."""
        code = """
        pub enum ChainState {
            Linked { next: Option<Box<dyn StdError + 'static>> },
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("+ )", zig)
        self.assertNotIn("+ >", zig)

    def test_nested_fn_decl_in_function_body_lowering(self) -> None:
        """Verify inner nested fn record_graft() inside function body lowers to const record_graft = struct { ... }."""
        code = """
        pub fn outer() {
            fn inner_helper(x: i32) -> i32 {
                return x + 1;
            }
            let y = inner_helper(41);
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("    fn inner_helper(", zig)
        self.assertIn("const inner_helper =", zig)

    def test_call_arg_leading_brace_expr_parens(self) -> None:
        """Verify call argument {}.into() is wrapped in parens (({}.into())) inside function call args."""
        code = """
        pub fn create_list(vals: Vec<u8>) {
            let list = try_new({}.into(), vals);
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn(", {}.into(),", zig)
        self.assertIn("({}).into()", zig)

    def test_reference_mut_prefix_lowering(self) -> None:
        """Verify &mut changes lowers to &changes without raw &mut syntax in Zig."""
        code = """
        pub fn update(changes: &mut Changes) {
            if let Some(c) = &mut changes {
                do_something();
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("&mut ", zig)

    def test_logical_not_on_is_null_method_call(self) -> None:
        """Verify !ptr.is_null() and !vec.is_empty() keep logical NOT ! instead of bitwise ~ in Zig."""
        code = """
        pub fn check(ptr: *const Node, vec: &[u8]) -> bool {
            if !ptr.is_null() && !vec.is_empty() {
                return true;
            }
            return false;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("~ptr.is_null()", zig)
        self.assertNotIn("~vec.is_empty()", zig)
        self.assertIn("!ptr.is_null()", zig)
        self.assertIn("!vec.is_empty()", zig)

    def test_array_index_as_cast_lowering(self) -> None:
        """Verify array[id as usize] lowers to array[@as(usize, id)] without raw as usize inside brackets."""
        code = """
        pub fn get_val(arr: &[u8], id: u8) -> u8 {
            return arr[id as usize];
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("[id as usize]", zig)
        self.assertIn("[@as(usize, id)]", zig)

    def test_single_letter_generic_type_fallback(self) -> None:
        """Verify single letter generic type F in fn from(p0: [2]F) generates pub const F = type; fallback."""
        code = """
        pub fn from(p0: [2]F) -> Point {
            return Point {};
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("pub const F = type;", zig)

    def test_undeclared_function_identifier_fallback(self) -> None:
        """Verify standalone call to function point(x, y) does not generate invalid pub const point = type; fallback."""
        code = """
        pub fn draw(x: f32, y: f32) {
            let p = point(x, y);
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("pub const point = type;", zig)
        self.assertIn("point(x, y)", zig)



    def test_and_or_reserved_keyword_escaping(self) -> None:
        """Verify Zig reserved keywords and / or are escaped as @"and" / @"or" and not emitted as invalid pub const and = type;."""
        code = """
        pub fn check_logic(and_val: bool, or_val: bool) -> bool {
            let and = and_val;
            let or = or_val;
            return and && or;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("pub const and = type;", zig)
        self.assertNotIn("pub const or = type;", zig)
        self.assertIn('@"and"', zig)
        self.assertIn('@"or"', zig)

    def test_pointer_type_fallback_header(self) -> None:
        """Verify *const Glyph and *const Cow trigger fallback type headers pub const Glyph = type; and pub const Cow = type;."""
        code = """
        pub fn process_glyph(g: *const Glyph, c: *const Cow) {
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("pub const Glyph = type;", zig)
        self.assertIn("pub const Cow = type;", zig)

    def test_unary_not_on_brace_starting_expr(self) -> None:
        """Verify !{}.@"0".is_null() wraps brace-starting target in parens so ! is not attached directly to {}."""
        code = """
        pub fn check_null(res: (Option<Node>, u32)) -> bool {
            if !res.0.is_null() {
                return true;
            }
            return false;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("!{", zig)

    def test_underscore_prefixed_var_discard(self) -> None:
        """Verify local variable starting with _ (e.g. let _cmd = 1;) receives _ = _cmd; discard in Zig."""
        code = """
        pub fn run_cmd() {
            let _cmd = 10;
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("_ = _cmd;", zig)

    def test_closure_expression_lowering(self) -> None:
        """Verify closure expression || node.children() lowers to Zig struct function runner."""
        code = """
        pub fn test_closure(flag: bool, node: Node) {
            let res = flag.then(|| node.children());
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("struct { fn run()", zig)
        self.assertIn("node.children()", zig)


    def test_unmutated_var_lowered_to_const(self) -> None:
        """Verify let mut x = 5; without subsequent mutation is lowered to const x = 5; in Zig."""
        code = """
        pub fn count_bytes() -> u32 {
            let mut byte_count = 0;
            return byte_count;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("var byte_count", zig)
        self.assertIn("const byte_count = 0;", zig)

    def test_field_access_on_brace_expr_parens(self) -> None:
        """Verify field/method access on {} receives parens ({}).map(Card) in Zig."""
        code = """
        pub fn process_card() {
            let res = Option::None.map(Card);
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("{}.map(", zig)

    def test_box_slice_type_mapping(self) -> None:
        """Verify map_type for &[Box<dyn Any>] maps to []const *anyopaque in Zig."""
        from rs2zig.lowering.stdlib_map import map_type
        mapped = map_type("&[Box<dyn Any>]")
        self.assertEqual(mapped, "[]const *anyopaque")

    def test_async_block_lowering(self) -> None:
        """Verify async move { ... } inside block_on is transpiled without leaking raw async block syntax."""
        code = """
        pub fn run_task() {
            block_on(async move {
                do_work();
            });
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("async move {", zig)

    def test_ref_expr_mutable_specifier(self) -> None:
        """Verify &mut self.0 does not produce invalid mut self.0 in Zig."""
        code = """
        pub fn get_ref(self: &mut Self) {
            Pin::new(&mut self.0);
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("&mut self.0", zig)

    def test_param_matching_function_name(self) -> None:
        """Verify fn ms(ms: u64) renames parameter ms to ms_param to avoid shadowing fn ms in Zig."""
        code = """
        pub fn ms(ms: u64) -> u64 {
            return ms + 1;
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("fn ms(ms_param:", zig)
        self.assertIn("ms_param + 1", zig)


if __name__ == "__main__":
    unittest.main()




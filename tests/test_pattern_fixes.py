"""
Unit Tests for Specific Rust-to-Zig Lowering Patterns (TDD Workflow).

Tests specific Rust AST constructs to verify transpiler accuracy without needing to re-transpile entire project directories.
"""

import unittest
from rs2zig.frontend.ts_parser import RustParser
from rs2zig.frontend.ast_builder import ASTBuilder
from rs2zig.backend.zig_emitter import ZigEmitter


class TestPatternFixes(unittest.TestCase):
    """Test suite verifying transpiler accuracy on isolated Rust syntax patterns."""

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

    def test_chained_generic_method_calls(self) -> None:
        """Verify long method chains with turbofish generics transform cleanly."""
        code = """
        pub fn test() {
            default_plugins
                .disable::<bevy::winit::WinitPlugin>()
                .disable::<bevy::a11y::AccessibilityPlugin>();
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("default_plugins.disable(bevy.winit.WinitPlugin)().disable(bevy.a11y.AccessibilityPlugin)();", zig)

    def test_unused_parameter_discarding(self) -> None:
        """Verify unused function parameters are auto-discarded with _ = param;."""
        code = """
        pub fn run(game_port: u16) {
            println!("Starting server...");
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("_ = game_port;", zig)

    def test_comptime_type_param_no_discard(self) -> None:
        """Verify comptime type parameters are not mistakenly discarded with _ = comptime T;."""
        code = """
        pub fn identity<T>(x: T) -> T {
            x
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("_ = comptime T;", zig)
        self.assertNotIn("_ = T;", zig)

    def test_channel_generic_lowering(self) -> None:
        """Verify channel::<T>() lowers to channel(T)()."""
        code = """
        pub fn setup() {
            let (tx, rx) = mpsc::channel::<u32>();
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("mpsc.channel(u32)()", zig)

    def test_closure_expression_lowering(self) -> None:
        """Verify closure expression inside argument list lowers cleanly."""
        code = """
        pub fn process() {
            items.iter().map(|x| x + 1);
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("items.iter().map", zig)

    def test_macro_args_discard_when_eprintln_dropped(self) -> None:
        """Verify parameter used only in dropped macro produces _ = param; in emitted Zig."""
        code = """
        pub fn run_lan(game_port: u16) {
            eprintln!("Listening on port {}", game_port);
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("_ = game_port;", zig)

    def test_block_attribute_item_ignored(self) -> None:
        """Verify Rust #[cfg(...)] block attribute inside a function does not emit invalid attribute statement."""
        code = """
        pub fn main() {
            #[cfg(target_os = "ios")]
            {
                println!("ios");
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("#[cfg", zig)

    def test_nested_option_type_mapping(self) -> None:
        """Verify Option<Option<T>> lowers to ?T without invalid double ? prefix."""
        code = """
        pub fn process(val: Option<Option<Vec<u8>>>) {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("??", zig)

    def test_reference_in_generic_type_mapping(self) -> None:
        """Verify Option<&T> lowers to ?*const T and Option<&mut T> lowers to ?*T."""
        code = """
        pub fn process(opt: Option<&MapEditorTestPlay>, opt_mut: Option<&mut MapEditorTestPlay>) {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("&", zig)

    def test_rust_lifetime_stripping(self) -> None:
        """Verify Rust lifetime annotations 'a, 'static are stripped from Zig type generic args."""
        code = """
        pub fn process(state: ChainState<'a, u32>) {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("'a", zig)
        self.assertIn("ChainState(u32)", zig)

    def test_const_decl_type_and_semicolon(self) -> None:
        """Verify const BOM: &str lowers to const BOM: []const u8 with single semicolon."""
        code = r"""
        pub const BOM: &str = "\u{feff}";
        """
        zig = self._transpile_code(code)
        self.assertNotIn("&str", zig)
        self.assertNotIn(";;", zig)
        self.assertIn("pub const BOM: []const u8 =", zig)

    def test_alloc_path_type_mapping(self) -> None:
        """Verify alloc::string::String and alloc::vec::Vec lower to Zig types cleanly."""
        code = """
        pub fn process(s: alloc::string::String, v: alloc::vec::Vec<u8>) -> std::string::String {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("alloc.string.String", zig)
        self.assertNotIn("std.string.String", zig)
        self.assertIn("[]u8", zig)

    def test_await_field_lowering(self) -> None:
        """Verify Rust expr.await lowers cleanly without invalid .await syntax."""
        code = """
        pub fn fetch() {
            let res = request().send().await;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn(".await", zig)
        self.assertIn("request().send()", zig)

    def test_fn_generic_params_lowering(self) -> None:
        """Verify Rust function generics fn foo<T: Send>() lower to (comptime T: type) in Zig."""
        code = """
        pub fn _assert_send_sync<T: Send + Sync>() {}
        """
        zig = self._transpile_code(code)
        self.assertNotIn("<T", zig)
        self.assertIn("comptime T: type", zig)

    def test_lifetime_in_struct_field_type(self) -> None:
        """Verify struct field generic types with lifetimes like slice.Iter('a, T.Item) strip lifetime 'a."""
        code = """
        pub struct IntoIter<'a, T> {
            iter: slice::Iter<'a, T>,
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("'a", zig)
        self.assertIn("slice.Iter(T)", zig)

    def test_unsized_slice_type_mapping(self) -> None:
        """Verify Rust unsized slice type [u8] lowers to Zig slice []u8."""
        code = """
        pub fn bytes_of(t: &[u8]) -> [u8] {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("[u8]", zig)
        self.assertIn("[]u8", zig)

    def test_as_cast_expression_lowering(self) -> None:
        """Verify Rust type cast expr as u64 lowers to Zig @as(u64, expr)."""
        code = """
        pub fn convert(x: i32) -> u64 {
            x as u64
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn(" as u64", zig)
        self.assertIn("@as(u64,", zig)

    def test_tuple_field_access_lowering(self) -> None:
        """Verify Rust tuple field access self.0 lowers to Zig self.@"0"."""
        code = """
        pub fn get_first(self: Point) -> i32 {
            self.0
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("self.0", zig)
        self.assertIn('self.@"0"', zig)

    def test_tuple_literal_lowering(self) -> None:
        """Verify Rust tuple literal (a, b, c) lowers to Zig anonymous struct .{ a, b, c }."""
        code = """
        pub fn make_tuple(a: i32, b: i32) {
            let t = &(a, b);
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("&(a, b)", zig)
        self.assertIn("&.{a, b}", zig)

    def test_fn_param_unsized_slice(self) -> None:
        """Verify fn parameter with unsized slice type [u8] lowers to []u8."""
        code = """
        pub fn parse(data: [u8]) {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("data: [u8]", zig)
        self.assertIn("data: []u8", zig)

    def test_nested_generics_bracket_matching(self) -> None:
        """Verify deeply nested generic types like Box<[CachePadded<RwLock<HashMap<K, V>>>]> lower cleanly."""
        code = """
        pub struct Shards<K, V> {
            shards: Box<[CachePadded<RwLock<HashMap<K, V>>>]>,
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("<", zig)
        self.assertIn("CachePadded(RwLock(HashMap(K, V)))", zig)

    def test_fixed_size_array_type(self) -> None:
        """Verify Rust fixed-size array type [u8; 16] lowers to Zig [16]u8 array type."""
        code = """
        pub fn format(src: [u8; 16]) -> [u8; 32] {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("[u8; 16]", zig)
        self.assertNotIn("[u8; 32]", zig)
        self.assertIn("[16]u8", zig)
        self.assertIn("[32]u8", zig)

    def test_fn_name_primitive_shadowing(self) -> None:
        """Verify function names that shadow Zig primitives/keywords are escaped with @""."""
        code = """
        pub fn u128() -> u128 {
            0
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("pub fn @\"u128\"() u128", zig)

    def test_lifetime_in_pointer_type(self) -> None:
        """Verify lifetime parameters like 'a, 'static, '_ in types are stripped."""
        code = """
        pub fn parse(s: &'static str, url: &'a Url) {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("'static", zig)
        self.assertNotIn("'a", zig)

    def test_tuple_return_type_lowering(self) -> None:
        """Verify Rust tuple return type (usize, usize) lowers to Zig struct { usize, usize }."""
        code = """
        pub fn process() -> (usize, usize) {
            (0, 0)
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("-> (usize, usize)", zig)
        self.assertIn("struct { @\"0\": usize, @\"1\": usize }", zig)

    def test_keyword_call_escaping(self) -> None:
        """Verify calls to functions named after Zig keywords like test(...) are escaped with @""."""
        code = """
        pub fn run() {
            let meta = test("#[foo]");
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("test(\"#[foo]\")", zig)
        self.assertIn("@\"test\"(\"#[foo]\")", zig)

    def test_impl_trait_parameter_lowering(self) -> None:
        """Verify Rust impl Trait parameter type impl Iterator lowers to Zig anytype."""
        code = """
        pub fn doc(trees: impl Iterator) -> bool {
            true
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("impl Iterator", zig)
        self.assertIn("trees: anytype", zig)

    def test_number_literal_type_suffix_stripping(self) -> None:
        """Verify Rust numeric type suffixes like _u64, u64, usize, i32 are stripped from literals."""
        code = """
        pub fn run() {
            let x = 1_u64;
            let y = 0x1FFFFFFF_u64;
            let z = 100usize;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("1_u64", zig)
        self.assertNotIn("0x1FFFFFFF_u64", zig)
        self.assertNotIn("100usize", zig)
        self.assertIn("1;", zig)
        self.assertIn("0x1FFFFFFF;", zig)
        self.assertIn("100;", zig)

    def test_slice_reference_type_mapping(self) -> None:
        """Verify Rust slice reference &[u8] lowers to Zig []const u8 instead of *const []u8."""
        code = """
        pub const DATA: &[u8] = b"data";
        """
        zig = self._transpile_code(code)
        self.assertNotIn("&[u8]", zig)
        self.assertNotIn("*const []u8", zig)
        self.assertIn("[]const u8", zig)

    def test_double_semicolon_prevention(self) -> None:
        """Verify const/static declarations do not emit double trailing semicolons (;;)."""
        code = """
        pub const MSG: &str = "hello";
        """
        zig = self._transpile_code(code)
        self.assertNotIn(";;", zig)

    def test_impl_trait_return_type_lowering(self) -> None:
        """Verify fn create_button() -> impl Bundle lowers to fn create_button() anytype."""
        code = """
        pub fn create_button() -> impl Bundle {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("impl Bundle", zig)
        self.assertIn("fn create_button() anytype", zig)

    def test_if_let_tuple_payload_capture(self) -> None:
        """Verify if let Some((color, reset_timer)) lowers cleanly without broken payload syntax."""
        code = """
        pub fn update() {
            if let Some((color, reset_timer)) = query.get_mut(entity) {
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("|(color, reset_timer|", zig)
        self.assertIn("if (query.get_mut(entity))", zig)

    def test_logical_operator_lowering(self) -> None:
        """Verify Rust logical operators && and || lower to Zig and / or operators."""
        code = """
        pub fn check(a: bool, b: bool) -> bool {
            (a && b) || !a
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("&&", zig)
        self.assertNotIn("||", zig)
        self.assertIn("and", zig)
        self.assertIn("or", zig)

    def test_while_let_loop_lowering(self) -> None:
        """Verify while let Some(x) = iter.next() lowers to Zig while (iter.next()) |x|."""
        code = """
        pub fn process() {
            while let Some(item) = stream.next() {
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("while (.Some", zig)
        self.assertIn("while (stream.next()) |item|", zig)

    def test_closure_unused_parameter_discarding(self) -> None:
        """Verify unused closure parameters are auto-discarded with _ = param; in closure helper struct."""
        code = """
        pub fn run() {
            let f = |x, y| x + 1;
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("_ = y;", zig)

    def test_ref_keyword_in_payload_capture(self) -> None:
        """Verify ref and ref mut keywords in if let payload capture are stripped for valid Zig capture."""
        code = """
        pub fn process() {
            if let Some(ref shared) = self.shared {
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("|ref shared|", zig)
        self.assertIn("|shared|", zig)

    def test_function_type_mapping(self) -> None:
        """Verify Rust function signature type fn(T) -> R lowers to Zig *const fn(T) R."""
        code = """
        pub struct Handler<T> {
            callback: fn(T) -> bool,
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("callback: fn(T)", zig)
        self.assertIn("*const fn(T) bool", zig)

    def test_raw_string_literal_lowering(self) -> None:
        """Verify Rust raw string literals r"[0-9]" and r#"hello"# lower to Zig string literals "[0-9]"."""
        code = """
        pub fn run() {
            let pat = r"[0-9]";
            let msg = r#"hello"#;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("r\"[0-9]\"", zig)
        self.assertNotIn("r#\"hello\"#", zig)
        self.assertIn("\"[0-9]\"", zig)
        self.assertIn("\"hello\"", zig)

    def test_array_reference_lowering(self) -> None:
        """Verify Rust array reference &["is_match", "find"] lowers to Zig &.{ "is_match", "find" }."""
        code = """
        pub fn run() {
            let args = &["is_match", "find"];
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("&[\"is_match\"", zig)
        self.assertIn("&.{\"is_match\", \"find\"}", zig)

    def test_raw_pointer_type_lowering(self) -> None:
        """Verify Rust raw pointer types (*mut T, *const 'a T, *mut [u8]) map cleanly to Zig pointer types (*T, *const T, []u8)."""
        code = """
        pub struct LruEntry {
            prev: *mut LruEntry,
            mutex: *const 'a Mutex,
            buf: *mut [u8],
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("*mut LruEntry", zig)
        self.assertNotIn("*const 'a Mutex", zig)
        self.assertNotIn("*mut [u8]", zig)
        self.assertIn("prev: *LruEntry", zig)
        self.assertIn("mutex: *const Mutex", zig)
    def test_unit_return_expression_lowering(self) -> None:
        """Verify Rust return () lowers to clean Zig return without invalid tuple syntax."""
        code = """
        pub fn run() {
            return ();
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("return ();", zig)
        self.assertIn("return;", zig)

    def test_closure_pattern_parameter_lowering(self) -> None:
        """Verify closures with tuple pattern parameters |res, (x, y)| build clean struct wrappers in Zig."""
        code = """
        pub fn fold_items() {
            let res = items.fold(None, |res, (x, y)| res);
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("|res, (x, y)|", zig)
    def test_reserved_keyword_parameter_escaping(self) -> None:
        """Verify reserved Zig keywords (test, error) in parameter names are escaped with @"..."."""
        code = """
        pub fn run_test(test: i32, error: u32) {
            let res = test + error as i32;
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("@\"test\": i32", zig)
        self.assertIn("@\"error\": u32", zig)

    def test_unsafe_block_lowering(self) -> None:
        """Verify Rust unsafe { ... } blocks unwrap cleanly into Zig blocks without raw unsafe keywords."""
        code = """
        pub fn run() {
            unsafe {
                let x = 42;
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("unsafe {", zig)

    def test_byte_string_literal_lowering(self) -> None:
        """Verify Rust byte string literal b"hello" lowers to Zig string literal "hello"."""
        code = """
        pub fn run() {
            let buf = b"hello";
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("b\"hello\"", zig)
        self.assertIn("\"hello\"", zig)

    def test_multiline_string_literal_newline_escaping(self) -> None:
        """Verify Rust multiline string literals with raw newlines escape newlines cleanly for Zig."""
        code = """
        pub fn run() {
            let s = "line1\nline2";
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("line1\nline2", zig)
    def test_reserved_keyword_module_import_escaping(self) -> None:
        """Verify module imports named after reserved Zig keywords (error.zig) are escaped as @"error"."""
        code = """
        pub fn run() {
            let res = error::get_val();
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("const error =", zig)
        self.assertIn("const @\"error\" =", zig)

    def test_compound_assignment_try_expression_lowering(self) -> None:
        """Verify Rust pos += func()?; lowers to Zig pos += try func(); without trailing ? or parentheses around assignment."""
        code = """
        pub fn run() {
            pos += pre.find(&haystack[pos..])?;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("pos += pre.find", zig)
        self.assertNotIn(")?; ", zig)
        self.assertIn("pos += try pre.find(", zig)

    def test_standalone_range_expression_lowering(self) -> None:
        """Verify Rust standalone range expression 0..cap() lowers to Zig struct .{ .start = 0, .end = cap() } while slice ranges buf[0..10] preserve indexing syntax."""
        code = """
        pub fn run() {
            let it = 0..self.capacity();
            let slice = &buf[0..10];
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("0..self.capacity()", zig)
        self.assertIn(".{ .start = 0, .end = self.capacity() }", zig)
        self.assertIn("buf[0..10]", zig)

    def test_array_type_with_generics_lowering(self) -> None:
        """Verify Rust fixed-size array types with generic parameters [MaybeUninit<u8>; 40] lower to Zig [40]MaybeUninit(u8)."""
        code = """
        pub struct Buf {
            bytes: [MaybeUninit<u8>; 40],
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("bytes: [MaybeUninit(u8),", zig)
        self.assertIn("bytes: [40]MaybeUninit(u8)", zig)

    def test_inner_block_const_decl_lowering(self) -> None:
        """Verify const item inside function block BOM: &str = ... lowers to Zig const BOM: []const u8 = ... without double semicolon."""
        code = """
        pub fn parse_file() {
            const BOM: &str = "\\u{feff}";
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn(";;", zig)
        self.assertNotIn(": &str =", zig)
        self.assertIn("const BOM: []const u8 =", zig)

    def test_struct_and_enum_field_keyword_escaping(self) -> None:
        """Verify struct fields and enum variants named after reserved keywords (error, test, const) are escaped as @\"error\"."""
        code = """
        pub struct ErrorInfo {
            pub error: u32,
            pub test: bool,
        }
        pub enum Mode {
            Error,
            Test(u32),
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("@\"error\": u32", zig)
        self.assertIn("@\"test\": bool", zig)

    def test_nested_function_in_block_lowering(self) -> None:
        """Verify nested function item inside a block lowers to clean Zig function definition without raw -> arrow syntax."""
        code = """
        pub fn test_peek() {
            fn assert(input: ParseStream) -> Result<()> {
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("->", zig)
        self.assertIn("fn assert(input: ParseStream) anyerror!void", zig)

    def test_fn_pointer_void_return_type_mapping(self) -> None:
        """Verify Rust function pointer types without return type fn(Cursor) map to Zig *const fn(Cursor) void."""
        code = """
        pub struct Marker {
            marker: *const fn(Cursor),
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("fn(Cursor) )", zig)
        self.assertIn("*const fn(Cursor) void", zig)

    def test_impl_trait_return_type_lowering(self) -> None:
        """Verify function returning impl Trait lowers return type to type instead of invalid anytype."""
        code = """
        pub fn naive_iter() -> impl Iterator {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("fn naive_iter() anytype", zig)
        self.assertIn("fn naive_iter() type", zig)

    def test_parenthesized_generic_type_lowering(self) -> None:
        """Verify parenthesized return types like (Rc<Cell<Unexpected>>) lower cleanly to Rc(Cell(Unexpected)) without leading parens on base type."""
        code = """
        pub fn inner_unexpected() -> (Rc<Cell<Unexpected>>) {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("(Rc(", zig)
        self.assertIn("fn inner_unexpected() *Cell(Unexpected)", zig)

    def test_shadow_import_name_collision_lowering(self) -> None:
        """Verify module import 'parse' alongside function 'pub fn parse()' renames import to avoid duplicate struct member error."""
        code = """
        mod parse;
        pub fn parse() {
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("const parse = @import", zig)
        self.assertIn("fn parse()", zig)


if __name__ == "__main__":
    unittest.main()







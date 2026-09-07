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
        self.assertIn("struct { usize, usize }", zig)

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


if __name__ == "__main__":
    unittest.main()

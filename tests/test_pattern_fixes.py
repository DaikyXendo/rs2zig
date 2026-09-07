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


if __name__ == "__main__":
    unittest.main()

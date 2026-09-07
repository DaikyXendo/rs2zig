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


if __name__ == "__main__":
    unittest.main()

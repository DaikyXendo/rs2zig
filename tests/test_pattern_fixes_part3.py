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


if __name__ == "__main__":
    unittest.main()

"""Unit test suite for isolated Rust-to-Zig pattern fixes (Part 2)."""

import unittest
from rs2zig.frontend.ts_parser import RustParser
from rs2zig.frontend.ast_builder import ASTBuilder
from rs2zig.backend.zig_emitter import ZigEmitter


class TestPatternFixesPart2(unittest.TestCase):
    """Test cases for transpiler fixes part 2."""

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

    def test_token_bracket_macro_type_lowering(self) -> None:
        """Verify Token![|] or Token![,] macro type syntax lowers cleanly to Token without invalid brackets."""
        code = """
        pub struct Items {
            p: Punctuated<Lit, Token![|]>,
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("Token![|]", zig)
        self.assertIn("Punctuated(Lit, Token)", zig)

    def test_return_unit_expr_lowering(self) -> None:
        """Verify return () in Rust functions lowers to return; in Zig without parens."""
        code = """
        pub fn process() {
            return ();
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("return ();", zig)
        self.assertIn("return;", zig)

    def test_match_arm_unit_expr_lowering(self) -> None:
        """Verify match arm returning () like .Ident(_) => () lowers to .Ident => {} in Zig."""
        code = """
        pub fn check(pat: Pat) {
            match pat {
                Pat::Ident(_) => (),
                _ => {},
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("=> (),", zig)
        self.assertIn("=> {},", zig)

    def test_unit_struct_decl_lowering(self) -> None:
        """Verify unit struct Foo; lowers to struct {} in Zig."""
        code = """
        pub struct Marker;
        """
        zig = self._transpile_code(code)
        self.assertIn("pub const Marker = struct {", zig)

    def test_byte_char_literal_lowering(self) -> None:
        """Verify b'a' byte character literal lowers to 'a' in Zig."""
        code = """
        pub fn get_byte() -> u8 {
            return b'a';
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("b'a'", zig)
        self.assertIn("'a'", zig)

    def test_array_literal_initializer_lowering(self) -> None:
        """Verify [0; 16] array initializer lowers to [_]u8{0} ** 16 in Zig."""
        code = """
        pub fn get_buf() -> [u8; 16] {
            return [0; 16];
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("[0; 16]", zig)

    def test_tuple_field_index_access_lowering(self) -> None:
        """Verify tuple field access self.0 lowers to self.@"0" in Zig."""
        code = """
        pub fn get_first(s: &TupleStruct) -> u8 {
            return s.0;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("s.0", zig)
        self.assertIn('s.@"0"', zig)

    def test_primitive_name_module_import_escaping(self) -> None:
        """Verify import of module named u8 or char is escaped properly."""
        code = """
        use char;
        """
        zig = self._transpile_code(code)
        self.assertIn("pub const char =", zig)

    def test_trailing_dot_float_literal_lowering(self) -> None:
        """Verify 1. or 0. floating point literal with trailing dot lowers to 1.0 or 0.0 in Zig."""
        code = """
        pub fn get_val() -> f64 {
            let x = 1.;
            return x;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("1.;", zig)
        self.assertIn("1.0;", zig)

    def test_multiple_discard_statement_lowering(self) -> None:
        """Verify multiple discard let _ = x; statements emit cleanly."""
        code = """
        pub fn process(x: i32) {
            let _ = x;
            let _ = x;
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("_ = x;", zig)

    def test_raw_field_name_struct_initializer(self) -> None:
        """Verify struct initializer with raw identifier field name .r#type(val) lowers to .@"type"(val)."""
        code = """
        pub fn create() -> Item {
            return Item { r#type: 1 };
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn(".r#type", zig)
        self.assertIn('.@"type"', zig)


if __name__ == "__main__":
    unittest.main()

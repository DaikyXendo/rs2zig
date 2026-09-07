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
        """Verify unit struct declaration struct BreakRules; lowers to const BreakRules = struct {}; in Zig."""
        code = """
        pub struct BreakRules;
        """
        zig = self._transpile_code(code)
        self.assertNotIn("struct BreakRules;", zig)
        self.assertIn("const BreakRules = struct {", zig)

    def test_byte_char_literal_lowering(self) -> None:
        """Verify byte character literal b'/' lowers to Zig character literal '/' without b prefix."""
        code = """
        pub fn check(b: u8) -> bool {
            b == b'/'
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("b'/'", zig)
        self.assertIn("'/'", zig)

    def test_array_literal_initializer_lowering(self) -> None:
        """Verify array literal elements [X, Y] lower to Zig anonymous struct initializer .{ X, Y }."""
        code = """
        pub fn init() {
            let arr = [X, Y];
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("[X, Y]", zig)
        self.assertIn(".{X, Y}", zig)

    def test_tuple_field_index_access_lowering(self) -> None:
        """Verify tuple numeric index access it.1 lowers to Zig field access it.@"1"."""
        code = """
        pub fn get_second(it: Pair) {
            let x = it.1;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("it.1;", zig)
        self.assertIn("it.@\"1\";", zig)

    def test_primitive_name_module_import_escaping(self) -> None:
        """Verify module import named after primitive type like mod usize; escapes module name as @"usize"."""
        code = """
        pub fn run() {
            let x = usize::val();
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("const usize =", zig)
        self.assertIn("const @\"usize\" =", zig)

    def test_trailing_dot_float_literal_lowering(self) -> None:
        """Verify float literals ending with a dot like 0. or 1. lower to 0.0 or 1.0 in Zig."""
        code = """
        pub fn get_val() -> f64 {
            let x = 0.;
            let y = 1.;
            return 0.0;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("0.;", zig)
        self.assertNotIn("1.;", zig)
        self.assertIn("0.0;", zig)
        self.assertIn("1.0;", zig)

    def test_multiple_discard_statement_lowering(self) -> None:
        """Verify multiple variable discards like _ = a, b; split into separate _ = a; _ = b; statements in Zig."""
        code = """
        pub fn process(a: i32, b: i32) {
            _ = a, b;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("_ = a, b;", zig)
        self.assertIn("_ = a;", zig)
        self.assertIn("_ = b;", zig)

    def test_unit_expression_call_arg_lowering(self) -> None:
        """Verify unit expression () passed as function argument lowers to {} in Zig."""
        code = """
        pub fn send_signal(tx: Sender) {
            tx.send(());
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("send(())", zig)
        self.assertIn("send({})", zig)

    def test_return_struct_init_semicolon_lowering(self) -> None:
        """Verify return statement returning struct initializer like return {} ends with semicolon in Zig."""
        code = """
        pub fn get_empty() {
            return {};
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("return {};", zig)

    def test_struct_init_assignment_semicolon_lowering(self) -> None:
        """Verify struct initializer assignment like from = .{a, b} ends with semicolon in Zig."""
        code = """
        pub fn swap_pair(from: Pair) {
            from = [from.1, from.0];
        }
        """
        zig = self._transpile_code(code)
        self.assertIn("from = .{from.@\"1\", from.@\"0\"};", zig)

    def test_closure_tuple_destructuring_param_lowering(self) -> None:
        """Verify closure parameter with tuple destructuring |res, (x, y)| cleans parameter name to valid identifier."""
        code = """
        pub fn fold_points() {
            let res = items.fold(None, |res, (x, y)| {
                return res;
            });
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("|res,", zig)
        self.assertNotIn("(x, y):", zig)
        self.assertIn("fn run(", zig)

    def test_dyn_trait_type_lowering(self) -> None:
        """Verify dyn Error and dyn Trait + Send types lower to anyerror/anyopaque in Zig."""
        code = """
        pub fn main() -> Result<void, dyn Error> {
            return Ok(());
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("dyn Error", zig)
        self.assertIn("anyerror", zig)

    def test_phantom_data_struct_field_lowering(self) -> None:
        """Verify PhantomData<T> struct fields lower to valid void fields without empty types."""
        code = """
        pub struct Icon {
            _marker: PhantomData<T>,
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("_marker: ,", zig)
        self.assertIn("_marker: void,", zig)

    def test_function_local_use_statement_lowering(self) -> None:
        """Verify use statements inside function bodies do not emit invalid use ...; in Zig."""
        code = """
        pub fn init() {
            use tracing_subscriber::filter;
            let x = 1;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("use tracing_subscriber", zig)
        self.assertNotIn("use filter;", zig)

    def test_self_return_type_lowering(self) -> None:
        """Verify Self return type in struct methods lowers to struct name or @This()."""
        code = """
        pub struct OpenOptions {}

        impl OpenOptions {
            pub fn new() -> Self {
                OpenOptions {}
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("fn new() Self {", zig)
        self.assertIn("fn new() OpenOptions {", zig)

    def test_raw_identifier_escaping(self) -> None:
        """Verify Rust raw identifiers like r#type or r#match escape cleanly as @"type" or @"match" in Zig."""
        code = """
        pub struct FieldInfo {
            pub r#type: u32,
            pub r#match: bool,
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("r#type", zig)
        self.assertNotIn("r#match", zig)
        self.assertIn("@\"type\": u32,", zig)
        self.assertIn("@\"match\": bool,", zig)

    def test_block_local_struct_decl_lowering(self) -> None:
        """Verify struct declarations inside function blocks lower to const Name = struct {}; in Zig."""
        code = """
        pub fn process() {
            struct DatetimeVisitor;
            let x = 1;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("struct DatetimeVisitor;", zig)
        self.assertIn("const DatetimeVisitor = struct {", zig)

    def test_match_arm_if_guard_lowering(self) -> None:
        """Verify match arm with if guard like .Assign(s) if s.is_empty() => {} lowers to if (s.is_empty()) {} in Zig."""
        code = """
        pub fn check_expr(e: Expr) {
            match e {
                Expr::Assign(s) if s.is_empty() => {},
                _ => {},
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("if s.is_empty() =>", zig)
        self.assertIn("if (s.is_empty())", zig)

    def test_as_cast_expression_lowering(self) -> None:
        """Verify Rust as cast expressions like (n / 8) as usize lower to @as(usize, (n / 8)) in Zig."""
        code = """
        pub fn get_byte(n: usize) -> usize {
            let idx = (n / 8) as usize;
            return idx;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("as usize", zig)
        self.assertIn("@as(usize,", zig)

    def test_pointer_as_cast_lowering(self) -> None:
        """Verify pointer as casts like ptr as *mut u8 lower to @ptrCast(p) in Zig."""
        code = """
        pub fn cast_ptr(p: *const u8) {
            let mut_p = p as *mut u8;
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("as *mut", zig)
        self.assertIn("@ptrCast(", zig)

    def test_atomic_types_lowering(self) -> None:
        """Verify Rust atomic types AtomicUsize, AtomicBool, AtomicU32 lower to std.atomic.Value in Zig."""
        code = """
        pub struct ReMutex {
            owner: AtomicUsize,
            flag: AtomicBool,
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("owner: AtomicUsize", zig)
        self.assertIn("owner: std.atomic.Value(usize)", zig)
        self.assertIn("flag: std.atomic.Value(bool)", zig)

    def test_multiple_discard_closure_syntax(self) -> None:
        """Verify tuple discard _ = (x, y); format into separate valid Zig statements."""
        code = """
        pub fn check(x: i32, y: i32) {
            _ = (x, y);
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("_ = x, y;", zig)
        self.assertIn("_ = x;", zig)
        self.assertIn("_ = y;", zig)

    def test_closure_param_type_cleaning(self) -> None:
        """Verify closure parameter types like |res: Option<T>, (x, y)| clean parameter names without colon types."""
        code = """
        pub fn fold_items() {
            let res = items.fold(None, |res: Option<i32>, (x, y)| {
                return res;
            });
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn(": Option", zig)
        self.assertNotIn("(x, y)", zig)
        self.assertIn("fn run(", zig)

    def test_duplicate_field_and_method_name_collision(self) -> None:
        """Verify struct with method having exact same name as a field renames method to get_<name> in Zig."""
        code = """
        pub struct SMBIOSInfo {
            pub length: u8,
        }

        impl SMBIOSInfo {
            pub fn length(&self) -> u8 {
                self.length
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("fn length(self:", zig)
        self.assertIn("fn get_length(self:", zig)

    def test_tuple_type_field_name_lowering(self) -> None:
        """Verify Rust tuple types (A, B) lower to valid Zig struct { @"0": A, @"1": B }."""
        code = """
        pub fn get_pair() -> (f64, f64) {
            return (0.0, 0.0);
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("struct { f64, f64 }", zig)
        self.assertIn("struct { @\"0\": f64, @\"1\": f64 }", zig)

    def test_struct_init_field_shorthand_lowering(self) -> None:
        """Verify Rust struct init field shorthand Point { x, y } preserves fields in Zig . { .x = x, .y = y }."""
        code = """
        pub fn create_point(x: f64, y: f64) -> Point {
            Point { x, y }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("Point { }", zig)
        self.assertIn(".x = x", zig)
        self.assertIn(".y = y", zig)

    def test_bitwise_not_operator_lowering(self) -> None:
        """Verify Rust bitwise NOT on masks/flags !(a & b) lowers to ~ in Zig."""
        code = """
        pub fn clear_mask(a: u32, b: u32) -> u32 {
            a & !(b)
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn("!(b)", zig)
        self.assertIn("~b", zig)

    def test_raw_field_name_struct_initializer(self) -> None:
        """Verify struct initializer with r#type field name lowers to .@"type" in Zig."""
        code = """
        pub fn init_field() -> FieldInfo {
            FieldInfo {
                r#type: 1,
            }
        }
        """
        zig = self._transpile_code(code)
        self.assertNotIn(".r#type =", zig)
        self.assertIn(".@\"type\" = 1", zig)

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


if __name__ == "__main__":
    unittest.main()


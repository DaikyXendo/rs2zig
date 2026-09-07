"""
AST and Intermediate Representation (IR) node definitions for rs2zig.

Defines typed dataclasses for representing parsed Rust elements and lowerable Zig AST nodes.
"""

from typing import List, Optional, Union, Any
from dataclasses import dataclass, field


@dataclass
class ASTNode:
    """Base dataclass for all AST and IR nodes."""
    pass


@dataclass
class GenericParam(ASTNode):
    """Generic parameter definition (e.g. <T: Display>)."""
    name: str
    bounds: List[str] = field(default_factory=list)


@dataclass
class Attribute(ASTNode):
    """Attribute definition (e.g. #[derive(Component)])."""
    name: str
    args: List[str] = field(default_factory=list)


@dataclass
class TypeNode(ASTNode):
    """Represents a type in Rust or lowered Zig representation."""
    name: str
    is_mutable: bool = False
    is_reference: bool = False
    is_slice: bool = False
    is_raw_pointer: bool = False
    generic_args: List['TypeNode'] = field(default_factory=list)

    def __str__(self) -> str:
        """String representation of type."""
        prefix = ""
        if self.is_reference:
            prefix += "&mut " if self.is_mutable else "&"
        elif self.is_slice:
            prefix += "[]"
        base = self.name
        if self.generic_args:
            args_str = ", ".join(str(arg) for arg in self.generic_args)
            base += f"<{args_str}>"
        return f"{prefix}{base}"


@dataclass
class Expr(ASTNode):
    """Base dataclass for expressions."""
    pass


@dataclass
class LiteralExpr(Expr):
    """Literal expression (integer, float, string, boolean, char)."""
    value: str
    kind: str  # 'int', 'float', 'string', 'bool', 'char'


@dataclass
class IdentifierExpr(Expr):
    """Identifier reference."""
    name: str


@dataclass
class BinaryExpr(Expr):
    """Binary operation expression (e.g., a + b, x == y)."""
    left: Expr
    op: str
    right: Expr


@dataclass
class UnaryExpr(Expr):
    """Unary operation expression (e.g., -x, !flag, *ptr, &val)."""
    op: str
    operand: Expr


@dataclass
class CallExpr(Expr):
    """Function or method call expression."""
    callee: Expr
    args: List[Expr] = field(default_factory=list)


@dataclass
class FieldAccessExpr(Expr):
    """Field access expression (e.g., obj.field)."""
    target: Expr
    field_name: str


@dataclass
class StructFieldInit(ASTNode):
    """Single field initializer inside a struct initialization."""
    field_name: str
    value: Expr


@dataclass
class StructInitExpr(Expr):
    """Struct initialization expression (e.g., Point { x: 10, y: 20 })."""
    struct_name: str
    fields: List[StructFieldInit] = field(default_factory=list)


@dataclass
class MacroCallExpr(Expr):
    """Macro invocation (e.g., println!("hello {}"), format!(...))."""
    macro_name: str
    args: List[Expr] = field(default_factory=list)
    raw_args_str: str = ""


@dataclass
class TryExpr(Expr):
    """Try expression corresponding to Rust ? operator (e.g. expr?)."""
    operand: Expr


@dataclass
class OptionalUnwrapExpr(Expr):
    """Unwrap expression corresponding to expr.unwrap()."""
    operand: Expr


@dataclass
class MatchArm(ASTNode):
    """Single arm in a match or switch statement (pattern => body)."""
    pattern: str
    body: Expr
    guard: Optional[Expr] = None


@dataclass
class MatchExpr(Expr):
    """Match expression/statement (match target { pat => body, ... })."""
    target: Expr
    arms: List[MatchArm] = field(default_factory=list)


@dataclass
class ReturnExpr(Expr):
    """Return statement or expression."""
    value: Optional[Expr] = None


@dataclass
class Stmt(ASTNode):
    """Base dataclass for statements."""
    pass


@dataclass
class ExprStmt(Stmt):
    """Statement consisting of an expression followed by semicolon."""
    expr: Expr


@dataclass
class LetStmt(Stmt):
    """Variable binding statement (let [mut] var: Type = expr)."""
    name: str
    var_type: Optional[TypeNode]
    value: Optional[Expr]
    is_mutable: bool = False


@dataclass
class AssignStmt(Stmt):
    """Assignment statement (lhs = rhs or lhs += rhs)."""
    lhs: Expr
    op: str  # '=', '+=', '-=', '*=', '/=', '%='
    rhs: Expr


@dataclass
class BlockExpr(Expr):
    """Block of statements with an optional trailing expression."""
    stmts: List[Stmt] = field(default_factory=list)
    trailing_expr: Optional[Expr] = None


@dataclass
class IfExpr(Expr):
    """If expression/statement (if cond { then_block } else { else_block })."""
    condition: Expr
    then_block: BlockExpr
    else_block: Optional[Union[BlockExpr, 'IfExpr']] = None


@dataclass
class LoopExpr(Expr):
    """Loop expression/statement (while, for, infinite loop)."""
    loop_kind: str  # 'while', 'for', 'loop'
    condition: Optional[Expr] = None
    var_name: Optional[str] = None  # for loop iterator variable name
    iterable: Optional[Expr] = None  # for loop range or iterable
    body: BlockExpr = field(default_factory=BlockExpr)


@dataclass
class ClosureExpr(Expr):
    """Closure / lambda expression (e.g. |x: i32| x + 1)."""
    params: List['Param'] = field(default_factory=list)
    body: Expr = field(default_factory=BlockExpr)
    return_type: Optional[TypeNode] = None


@dataclass
class Param(ASTNode):
    """Function parameter definition."""
    name: str
    param_type: TypeNode
    is_mutable: bool = False
    is_self: bool = False


@dataclass
class FieldDecl(ASTNode):
    """Struct field declaration."""
    name: str
    field_type: TypeNode
    is_pub: bool = False


@dataclass
class FnDecl(ASTNode):
    """Function declaration."""
    name: str
    params: List[Param] = field(default_factory=list)
    return_type: Optional[TypeNode] = None
    body: Optional[BlockExpr] = None
    is_pub: bool = False
    generic_params: List[GenericParam] = field(default_factory=list)


@dataclass
class StructDecl(ASTNode):
    """Struct definition."""
    name: str
    fields: List[FieldDecl] = field(default_factory=list)
    is_pub: bool = False
    attributes: List[Attribute] = field(default_factory=list)
    generic_params: List[GenericParam] = field(default_factory=list)


@dataclass
class EnumVariantField(ASTNode):
    """Field inside an enum variant (e.g. V(i32) or V { val: i32 })."""
    name: Optional[str]
    field_type: TypeNode


@dataclass
class EnumVariant(ASTNode):
    """Single variant inside an enum definition."""
    name: str
    fields: List[EnumVariantField] = field(default_factory=list)


@dataclass
class EnumDecl(ASTNode):
    """Enum definition (simple enum or tagged union with payload)."""
    name: str
    variants: List[EnumVariant] = field(default_factory=list)
    is_pub: bool = False
    attributes: List[Attribute] = field(default_factory=list)


@dataclass
class TraitDecl(ASTNode):
    """Trait declaration definition."""
    name: str
    methods: List[FnDecl] = field(default_factory=list)
    is_pub: bool = False


@dataclass
class ImplBlock(ASTNode):
    """Impl block containing methods for a struct or enum, optionally implementing a trait."""
    struct_name: str
    trait_name: Optional[str] = None
    methods: List[FnDecl] = field(default_factory=list)


@dataclass
class ConstDecl(ASTNode):
    """Constant or static variable declaration (e.g. const BOM: &str = "...")."""
    name: str
    const_type: TypeNode
    value: Expr
    is_pub: bool = False
    is_static: bool = False


@dataclass
class SourceFile(ASTNode):
    """Top-level source file module container."""
    constants: List[ConstDecl] = field(default_factory=list)
    structs: List[StructDecl] = field(default_factory=list)
    enums: List[EnumDecl] = field(default_factory=list)
    traits: List[TraitDecl] = field(default_factory=list)
    functions: List[FnDecl] = field(default_factory=list)
    impls: List[ImplBlock] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)

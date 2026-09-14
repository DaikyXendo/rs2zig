"""
AST Builder for rs2zig.

Converts tree-sitter Rust CST (Concrete Syntax Tree) nodes into rs2zig IR dataclass nodes.
Delegates declaration building to decl_builder and expression building to expr_builder.
"""

import re
import logging
from typing import List, Optional
import tree_sitter

from rs2zig.ir.nodes import (
    SourceFile,
    ConstDecl,
    FnDecl,
    TypeNode,
    BlockExpr,
    Stmt,
    Expr,
    LetStmt,
    AssignStmt,
    ExprStmt,
    StructDecl,
    EnumDecl,
    EnumVariant,
    TraitDecl,
    ImplBlock,
)
from rs2zig.frontend.decl_builder import (
    get_node_type,
    build_const,
    build_struct,
    build_enum,
    build_enum_variant,
    build_trait,
    build_impl,
    build_function,
    build_type,
)
from rs2zig.frontend.expr_builder import build_expr, is_expr_node

logger = logging.getLogger("rs2zig.frontend.ast_builder")


class ASTBuilder:
    """Walks tree-sitter syntax nodes and constructs IR AST objects."""

    def __init__(self, code_bytes: bytes) -> None:
        """Initialize ASTBuilder with original source code bytes for exact text extraction.

        Args:
            code_bytes: Source code encoded as bytes.
        """
        self.code_bytes = code_bytes

    def get_text(self, node: tree_sitter.Node) -> str:
        """Extract substring text corresponding to a tree-sitter node.

        Args:
            node: tree_sitter node.

        Returns:
            Extracted text string.
        """
        if hasattr(node, "text") and isinstance(node.text, bytes):
            return node.text.decode("utf-8", errors="replace")
        return self.code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def build_source_file(self, root_node: tree_sitter.Node) -> SourceFile:
        """Build top-level SourceFile IR from tree-sitter source_file node.

        Args:
            root_node: Root node of CST (type: source_file).

        Returns:
            SourceFile AST container.
        """
        sf = SourceFile()
        for child in root_node.children:
            ntype = get_node_type(child)
            if ntype in ("const_item", "static_item"):
                sf.constants.append(self._build_const(child))
            elif ntype == "function_item":
                sf.functions.append(self._build_function(child))
            elif ntype == "struct_item":
                sf.structs.append(self._build_struct(child))
            elif ntype == "enum_item":
                sf.enums.append(self._build_enum(child))
            elif ntype == "trait_item":
                sf.traits.append(self._build_trait(child))
            elif ntype == "impl_item":
                sf.impls.append(self._build_impl(child))
            elif ntype == "use_declaration":
                text = self.get_text(child).replace("use ", "").replace(";", "").strip()
                if "{" in text and "}" in text:
                    body = text[text.find("{") + 1 : text.rfind("}")].strip()
                    words = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", body)
                    for w in words:
                        if w not in ("as", "crate", "self", "super", "pub"):
                            sf.imports.append(w)
                else:
                    parts = [p.strip() for p in text.split("::") if p.strip()]
                    if parts:
                        last_part = parts[-1].split(" as ")[0].strip()
                        if last_part and last_part.isidentifier() and last_part not in ("as", "crate", "self", "super", "pub"):
                            sf.imports.append(last_part)
            elif ntype == "mod_item":
                for c in child.children:
                    if c.type == "identifier":
                        mname = self.get_text(c)
                        if mname and mname.isidentifier():
                            sf.imports.append(mname)
                        break

        return sf

    def _build_const(self, node: tree_sitter.Node) -> ConstDecl:
        """Build ConstDecl from const_item or static_item node."""
        return build_const(self, node)

    def _build_struct(self, node: tree_sitter.Node) -> StructDecl:
        """Build StructDecl from struct_item node."""
        return build_struct(self, node)

    def _build_enum(self, node: tree_sitter.Node) -> EnumDecl:
        """Build EnumDecl from enum_item node."""
        return build_enum(self, node)

    def _build_enum_variant(self, node: tree_sitter.Node) -> EnumVariant:
        """Build EnumVariant from enum_variant node."""
        return build_enum_variant(self, node)

    def _build_trait(self, node: tree_sitter.Node) -> TraitDecl:
        """Build TraitDecl from trait_item node."""
        return build_trait(self, node)

    def _build_impl(self, node: tree_sitter.Node) -> ImplBlock:
        """Build ImplBlock from impl_item node."""
        return build_impl(self, node)

    def _build_function(self, node: tree_sitter.Node) -> FnDecl:
        """Build FnDecl from function_item node."""
        return build_function(self, node)

    def _build_type(self, node: tree_sitter.Node) -> TypeNode:
        """Build TypeNode from type syntax node."""
        return build_type(self, node)

    def _build_block(self, node: tree_sitter.Node) -> BlockExpr:
        """Build BlockExpr from block node."""
        stmts: List[Stmt] = []
        trailing_expr: Optional[Expr] = None

        children = [c for c in node.children if get_node_type(c) not in ("{", "}")]
        for idx, child in enumerate(children):
            ntype = get_node_type(child)
            if ntype in ("attribute_item", "inner_attribute_item", "use_declaration", "impl_item", "trait_item", "macro_definition") or ntype.startswith("attribute") or ntype.startswith("macro"):
                continue
            if ntype == "let_declaration":
                stmts.append(self._build_let_stmt(child))
            elif ntype in ("const_item", "static_item"):
                const_decl = self._build_const(child)
                stmts.append(
                    LetStmt(
                        name=const_decl.name,
                        var_type=const_decl.const_type,
                        value=const_decl.value,
                        is_mutable=False
                    )
                )
            elif ntype == "function_item":
                stmts.append(self._build_function(child))  # type: ignore
            elif ntype == "struct_item":
                stmts.append(self._build_struct(child))  # type: ignore
            elif ntype == "enum_item":
                stmts.append(self._build_enum(child))  # type: ignore
            elif ntype == "expression_statement":
                sub_expr = child.children[0] if child.children else None
                if sub_expr:
                    stmts.append(ExprStmt(expr=self._build_expr(sub_expr)))
            elif ntype == "assignment_expression":
                stmts.append(self._build_assign_stmt(child))
            elif idx == len(children) - 1 and self._is_expr_node(child):
                trailing_expr = self._build_expr(child)
            else:
                expr = self._build_expr(child)
                stmts.append(ExprStmt(expr=expr))

        return BlockExpr(stmts=stmts, trailing_expr=trailing_expr)

    def _build_let_stmt(self, node: tree_sitter.Node) -> LetStmt:
        """Build LetStmt from let_declaration node."""
        pattern_node = node.child_by_field_name("pattern")
        type_node = node.child_by_field_name("type")
        value_node = node.child_by_field_name("value")

        var_name = self.get_text(pattern_node) if pattern_node else "temp_var"
        is_mut = any(get_node_type(c) == "mutable_specifier" for c in node.children) or "mut " in var_name
        var_name = var_name.replace("mut ", "").strip()

        parsed_type = self._build_type(type_node) if type_node else None
        parsed_val = self._build_expr(value_node) if value_node else None

        return LetStmt(
            name=var_name,
            var_type=parsed_type,
            value=parsed_val,
            is_mutable=is_mut
        )

    def _build_assign_stmt(self, node: tree_sitter.Node) -> AssignStmt:
        """Build AssignStmt from assignment_expression node."""
        left = node.child_by_field_name("left")
        operator = node.child_by_field_name("operator")
        right = node.child_by_field_name("right")

        lhs_expr = self._build_expr(left) if left else IdentifierExpr(name="unknown")
        op_str = self.get_text(operator) if operator else "="
        rhs_expr = self._build_expr(right) if right else LiteralExpr(value="0", kind="int")

        return AssignStmt(lhs=lhs_expr, op=op_str, rhs=rhs_expr)

    def _build_expr(self, node: tree_sitter.Node) -> Expr:
        """Recursively build Expr node from tree-sitter node."""
        return build_expr(self, node)

    def _is_expr_node(self, node: tree_sitter.Node) -> bool:
        """Check if node represents an expression rather than statement."""
        return is_expr_node(node)

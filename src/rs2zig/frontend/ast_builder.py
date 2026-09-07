"""
AST Builder for rs2zig.

Converts tree-sitter Rust CST (Concrete Syntax Tree) nodes into rs2zig IR dataclass nodes.
"""

import logging
from typing import List, Optional, Union
import tree_sitter

from rs2zig.lowering.stdlib_map import map_type, _split_angle_brackets, _split_top_level_commas
from rs2zig.ir.nodes import (
    SourceFile,
    ConstDecl,
    FnDecl,
    Param,
    TypeNode,
    BlockExpr,
    Stmt,
    Expr,
    LetStmt,
    AssignStmt,
    ExprStmt,
    LiteralExpr,
    IdentifierExpr,
    BinaryExpr,
    UnaryExpr,
    CallExpr,
    FieldAccessExpr,
    StructInitExpr,
    StructFieldInit,
    MacroCallExpr,
    ReturnExpr,
    IfExpr,
    LoopExpr,
    StructDecl,
    FieldDecl,
    EnumDecl,
    EnumVariant,
    EnumVariantField,
    TraitDecl,
    GenericParam,
    Attribute,
    MatchExpr,
    MatchArm,
    TryExpr,
    OptionalUnwrapExpr,
    ClosureExpr,
    ImplBlock,
)

logger = logging.getLogger("rs2zig.frontend.ast_builder")


def get_node_type(node: tree_sitter.Node) -> str:
    """Safely get string node type (handles differences between tree-sitter versions).

    Args:
        node: tree_sitter Node object.

    Returns:
        Node type string.
    """
    return getattr(node, "type", getattr(node, "kind", ""))


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
        return sf

    def _build_const(self, node: tree_sitter.Node) -> ConstDecl:
        """Build ConstDecl from const_item or static_item node."""
        is_pub = any(get_node_type(c) == "visibility_modifier" for c in node.children)
        is_static = get_node_type(node) == "static_item"
        name_node = node.child_by_field_name("name")
        type_node = node.child_by_field_name("type")
        val_node = node.child_by_field_name("value")

        name = self.get_text(name_node) if name_node else "CONST_VAL"
        ctype = self._build_type(type_node) if type_node else TypeNode(name="anytype")
        val = self._build_expr(val_node) if val_node else LiteralExpr(value="0", kind="int")

        return ConstDecl(name=name, const_type=ctype, value=val, is_pub=is_pub, is_static=is_static)

    def _build_struct(self, node: tree_sitter.Node) -> StructDecl:
        """Build StructDecl from struct_item node."""
        name_node = node.child_by_field_name("name")
        struct_name = self.get_text(name_node) if name_node else "UnknownStruct"
        is_pub = any(get_node_type(child) == "visibility_modifier" for child in node.children)
        fields: List[FieldDecl] = []

        field_list = node.child_by_field_name("body")
        if field_list:
            for child in field_list.children:
                if get_node_type(child) == "field_declaration":
                    fname_node = child.child_by_field_name("name")
                    ftype_node = child.child_by_field_name("type")
                    if fname_node and ftype_node:
                        f_is_pub = any(get_node_type(c) == "visibility_modifier" for c in child.children)
                        fields.append(
                            FieldDecl(
                                name=self.get_text(fname_node),
                                field_type=self._build_type(ftype_node),
                                is_pub=f_is_pub
                            )
                        )

        return StructDecl(name=struct_name, fields=fields, is_pub=is_pub)

    def _build_enum(self, node: tree_sitter.Node) -> EnumDecl:
        """Build EnumDecl from enum_item node."""
        name_node = node.child_by_field_name("name")
        enum_name = self.get_text(name_node) if name_node else "UnknownEnum"
        is_pub = any(get_node_type(child) == "visibility_modifier" for child in node.children)

        variants: List[EnumVariant] = []
        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                if get_node_type(child) == "enum_variant":
                    variants.append(self._build_enum_variant(child))

        return EnumDecl(name=enum_name, variants=variants, is_pub=is_pub)

    def _build_trait(self, node: tree_sitter.Node) -> TraitDecl:
        """Build TraitDecl from trait_item node."""
        name_node = node.child_by_field_name("name")
        trait_name = self.get_text(name_node) if name_node else "UnknownTrait"
        is_pub = any(get_node_type(child) == "visibility_modifier" for child in node.children)
        methods: List[FnDecl] = []

        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                if get_node_type(child) in ("function_item", "function_signature_item"):
                    methods.append(self._build_function(child))

        return TraitDecl(name=trait_name, methods=methods, is_pub=is_pub)

    def _build_enum_variant(self, node: tree_sitter.Node) -> EnumVariant:
        """Build EnumVariant from enum_variant node."""
        name_node = node.child_by_field_name("name")
        vname = self.get_text(name_node) if name_node else self.get_text(node).split("{")[0].split("(")[0].strip()

        variant_fields: List[EnumVariantField] = []
        body_node = node.child_by_field_name("body")

        if body_node:
            for child in body_node.children:
                if get_node_type(child) == "field_declaration":
                    fn = child.child_by_field_name("name")
                    ft = child.child_by_field_name("type")
                    if ft:
                        variant_fields.append(
                            EnumVariantField(
                                name=self.get_text(fn) if fn else None,
                                field_type=self._build_type(ft)
                            )
                        )
                elif get_node_type(child) == "tuple_field":
                    ft = child.child_by_field_name("type") or child
                    variant_fields.append(
                        EnumVariantField(name=None, field_type=self._build_type(ft))
                    )

        return EnumVariant(name=vname, fields=variant_fields)

    def _build_impl(self, node: tree_sitter.Node) -> ImplBlock:
        """Build ImplBlock from impl_item node."""
        type_node = node.child_by_field_name("type")
        trait_node = node.child_by_field_name("trait")

        struct_name = self.get_text(type_node) if type_node else "UnknownType"
        trait_name = self.get_text(trait_node) if trait_node else None
        methods: List[FnDecl] = []

        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if get_node_type(child) in ("function_item", "function_signature_item"):
                    methods.append(self._build_function(child))

        return ImplBlock(struct_name=struct_name, trait_name=trait_name, methods=methods)

    def _build_function(self, node: tree_sitter.Node) -> FnDecl:
        """Build FnDecl from function_item node."""
        name_node = node.child_by_field_name("name")
        func_name = self.get_text(name_node) if name_node else "unnamed_fn"
        is_pub = any(get_node_type(child) == "visibility_modifier" for child in node.children)

        generic_params: List[GenericParam] = []
        type_params = node.child_by_field_name("type_parameters")
        if type_params:
            for child in type_params.children:
                if get_node_type(child) in ("type_parameter", "constrained_type_parameter", "type_identifier"):
                    gname = self.get_text(child).split(":")[0].strip()
                    if gname not in ("<", ">", ","):
                        generic_params.append(GenericParam(name=gname))

        params: List[Param] = []
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for child in params_node.children:
                ntype = get_node_type(child)
                if ntype == "parameter":
                    pattern_node = child.child_by_field_name("pattern")
                    type_node = child.child_by_field_name("type")
                    if pattern_node and type_node:
                        params.append(
                            Param(
                                name=self.get_text(pattern_node),
                                param_type=self._build_type(type_node)
                            )
                        )
                elif ntype == "self_parameter":
                    ref_child = any(get_node_type(c) == "&" for c in child.children)
                    mut_child = any(get_node_type(c) == "mut" for c in child.children)
                    params.append(
                        Param(
                            name="self",
                            param_type=TypeNode(name="Self", is_reference=ref_child, is_mutable=mut_child),
                            is_self=True
                        )
                    )

        ret_type_node = node.child_by_field_name("return_type")
        return_type = self._build_type(ret_type_node) if ret_type_node else None

        body_node = node.child_by_field_name("body")
        body = self._build_block(body_node) if body_node else None

        return FnDecl(
            name=func_name,
            params=params,
            return_type=return_type,
            body=body,
            is_pub=is_pub,
            generic_params=generic_params
        )

    def _build_type(self, node: tree_sitter.Node) -> TypeNode:
        """Build TypeNode from type syntax node."""
        text = self.get_text(node).strip()
        if text.startswith("->"):
            text = text[2:].strip()
        if text.startswith("(") and text.endswith(")") and "," not in text:
            text = text[1:-1].strip()
        is_raw_ptr = text.startswith("*const ") or text.startswith("*mut ")
        is_array_type = text.startswith("[") and text.endswith("]")
        if is_raw_ptr or is_array_type:
            is_ref = False
            is_mut = False
            clean_text = text
            generic_args = []
        else:
            is_ref = text.startswith("&")
            is_mut = "&mut " in text
            clean_text = text.lstrip("&").replace("mut ", "").strip()
            if clean_text.startswith("(") and clean_text.endswith(")") and "," not in clean_text:
                clean_text = clean_text[1:-1].strip()
            generic_args = []
            split_res = _split_angle_brackets(clean_text)
            if split_res:
                base_name, generic_str, _ = split_res
                for arg_part in _split_top_level_commas(generic_str):
                    if arg_part.strip() and not arg_part.strip().startswith("'"):
                        generic_args.append(TypeNode(name=arg_part.strip()))
                clean_text = base_name.strip()

        is_slice_type = clean_text.startswith("[") and clean_text.endswith("]") and ";" not in clean_text
        return TypeNode(
            name=clean_text,
            is_reference=is_ref,
            is_mutable=is_mut,
            is_slice=is_slice_type,
            is_raw_pointer=is_raw_ptr,
            generic_args=generic_args
        )

    def _build_block(self, node: tree_sitter.Node) -> BlockExpr:
        """Build BlockExpr from block node."""
        stmts: List[Stmt] = []
        trailing_expr: Optional[Expr] = None

        children = [c for c in node.children if get_node_type(c) not in ("{", "}")]
        for idx, child in enumerate(children):
            ntype = get_node_type(child)
            if ntype in ("attribute_item", "inner_attribute_item", "use_declaration") or ntype.startswith("attribute"):
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
        ntype = get_node_type(node)

        if ntype in ("integer_literal", "float_literal", "string_literal", "raw_string_literal", "boolean_literal", "char_literal"):
            k_map = {
                "integer_literal": "int",
                "float_literal": "float",
                "string_literal": "string",
                "raw_string_literal": "string",
                "boolean_literal": "bool",
                "char_literal": "char"
            }
            return LiteralExpr(value=self.get_text(node), kind=k_map.get(ntype, "int"))

        if ntype == "identifier":
            return IdentifierExpr(name=self.get_text(node))

        if ntype == "binary_expression":
            left_node = node.child_by_field_name("left")
            op_node = node.child_by_field_name("operator")
            right_node = node.child_by_field_name("right")
            return BinaryExpr(
                left=self._build_expr(left_node) if left_node else LiteralExpr("0", "int"),
                op=self.get_text(op_node) if op_node else "+",
                right=self._build_expr(right_node) if right_node else LiteralExpr("0", "int")
            )

        if ntype in ("assignment_expression", "compound_assignment_expr"):
            left_node = node.child_by_field_name("left") or (node.children[0] if len(node.children) > 2 else None)
            op_node = node.child_by_field_name("operator") or (node.children[1] if len(node.children) > 2 else None)
            right_node = node.child_by_field_name("right") or (node.children[2] if len(node.children) > 2 else None)
            return BinaryExpr(
                left=self._build_expr(left_node) if left_node else IdentifierExpr("lhs"),
                op=self.get_text(op_node) if op_node else "=",
                right=self._build_expr(right_node) if right_node else LiteralExpr("0", "int")
            )

        if ntype in ("unary_expression", "reference_expression"):
            op_node = node.child_by_field_name("operator") or (node.children[0] if len(node.children) > 0 else None)
            arg_node = node.child_by_field_name("argument") or node.child_by_field_name("value")
            if not arg_node and len(node.children) > 1:
                arg_node = node.children[1] if get_node_type(node.children[0]) in ("&", "-", "!") else node.children[-1]
            op_str = "&" if ntype == "reference_expression" else (self.get_text(op_node) if op_node else "-")
            return UnaryExpr(
                op=op_str,
                operand=self._build_expr(arg_node) if arg_node else LiteralExpr("0", "int")
            )

        if ntype == "generic_function":
            fn_node = node.child_by_field_name("function")
            if not fn_node and node.children:
                fn_node = node.children[0]
            type_args_node = node.child_by_field_name("type_arguments")
            if not type_args_node:
                for c in node.children:
                    if get_node_type(c) == "type_arguments":
                        type_args_node = c
                        break
            fn_expr = self._build_expr(fn_node) if fn_node else IdentifierExpr("unknown_generic_fn")
            type_args_str = self.get_text(type_args_node) if type_args_node else ""
            if type_args_str:
                if not type_args_str.startswith("::<"):
                    if type_args_str.startswith("<"):
                        type_args_str = "::" + type_args_str
                    else:
                        type_args_str = "::<" + type_args_str + ">"
            if isinstance(fn_expr, IdentifierExpr):
                return IdentifierExpr(name=f"{fn_expr.name}{type_args_str}")
            elif isinstance(fn_expr, FieldAccessExpr):
                return FieldAccessExpr(target=fn_expr.target, field_name=f"{fn_expr.field_name}{type_args_str}")
            return fn_expr

        if ntype == "type_cast_expression":
            val_node = node.child_by_field_name("value") or (node.children[0] if node.children else None)
            type_node = node.child_by_field_name("type") or (node.children[2] if len(node.children) > 2 else None)
            val_expr = self._build_expr(val_node) if val_node else IdentifierExpr("val")
            target_type_str = map_type(self._build_type(type_node)) if type_node else "anytype"
            if target_type_str.startswith("*") or target_type_str in ("_", "*mut _", "*const _"):
                return CallExpr(callee=IdentifierExpr("@ptrCast"), args=[val_expr])
            return CallExpr(callee=IdentifierExpr("@as"), args=[IdentifierExpr(target_type_str), val_expr])

        if ntype == "unsafe_block":
            block_node = node.child_by_field_name("block") or (node.children[1] if len(node.children) > 1 else None)
            return self._build_block(block_node) if block_node else BlockExpr()

        if ntype == "await_expression":
            operand_node = node.children[0] if node.children else None
            return self._build_expr(operand_node) if operand_node else IdentifierExpr("future")

        if ntype == "try_expression":
            operand_node = node.children[0] if node.children else None
            return TryExpr(operand=self._build_expr(operand_node) if operand_node else IdentifierExpr("res"))

        if ntype == "range_expression":
            left_node = node.child_by_field_name("left") or (node.children[0] if len(node.children) > 1 and get_node_type(node.children[0]) != ".." else None)
            right_node = node.child_by_field_name("right") or (node.children[-1] if len(node.children) > 1 and get_node_type(node.children[-1]) != ".." else None)
            left_expr = self._build_expr(left_node) if left_node else LiteralExpr("0", "int")
            right_expr = self._build_expr(right_node) if right_node else IdentifierExpr("len")
            parent_type = get_node_type(node.parent) if node.parent else ""
            if parent_type in ("index_expression", "for_expression"):
                return BinaryExpr(left=left_expr, op="..", right=right_expr)
            return StructInitExpr(
                struct_name=".",
                fields=[
                    StructFieldInit("start", left_expr),
                    StructFieldInit("end", right_expr)
                ]
            )

        if ntype == "match_expression":
            val_node = node.child_by_field_name("value")
            body_node = node.child_by_field_name("body")
            arms: List[MatchArm] = []

            if body_node:
                for child in body_node.children:
                    if get_node_type(child) == "match_arm":
                        pat_node = child.child_by_field_name("pattern")
                        arm_val_node = child.child_by_field_name("value")
                        if pat_node and arm_val_node:
                            arms.append(
                                MatchArm(
                                    pattern=self.get_text(pat_node),
                                    body=self._build_expr(arm_val_node)
                                )
                            )

            return MatchExpr(
                target=self._build_expr(val_node) if val_node else IdentifierExpr("val"),
                arms=arms
            )

        if ntype == "call_expression":
            fn_node = node.child_by_field_name("function")
            args_node = node.child_by_field_name("arguments")
            callee_text = self.get_text(fn_node) if fn_node else ""

            if callee_text.endswith(".unwrap"):
                target_expr = self._build_expr(fn_node.child_by_field_name("value")) if fn_node and fn_node.type == "field_expression" else IdentifierExpr("opt")
                return OptionalUnwrapExpr(operand=target_expr)

            args: List[Expr] = []
            if args_node:
                for child in args_node.children:
                    if get_node_type(child) not in ("(", ")", ","):
                        args.append(self._build_expr(child))

            return CallExpr(
                callee=self._build_expr(fn_node) if fn_node else IdentifierExpr("unknown_fn"),
                args=args
            )

        if ntype == "array_expression":
            text = self.get_text(node)
            if ";" in text:
                inner = text.strip("[]")
                parts = inner.split(";", 1)
                val_clean = parts[0].strip().replace("_u8", "").replace("u8", "")
                count_clean = parts[1].strip()
                return LiteralExpr(value=f"([_]u8{{{val_clean}}} ** {count_clean})", kind="array")
            else:
                elem_nodes = [c for c in node.children if get_node_type(c) not in ("[", "]", ",")]
                if elem_nodes:
                    inits = [
                        StructFieldInit(field_name=str(idx), value=self._build_expr(c))
                        for idx, c in enumerate(elem_nodes)
                    ]
                    return StructInitExpr(struct_name=".", fields=inits)

        if ntype == "field_expression":
            val_node = node.child_by_field_name("value")
            field_node = node.child_by_field_name("field")
            return FieldAccessExpr(
                target=self._build_expr(val_node) if val_node else IdentifierExpr("obj"),
                field_name=self.get_text(field_node) if field_node else "field"
            )

        if ntype == "struct_expression":
            name_node = node.child_by_field_name("name")
            body_node = node.child_by_field_name("body")
            inits: List[StructFieldInit] = []
            if body_node:
                for child in body_node.children:
                    nt = get_node_type(child)
                    if nt in ("field_initializer", "shorthand_field_initializer"):
                        fn = child.child_by_field_name("field") or (child if nt == "shorthand_field_initializer" else None)
                        fv = child.child_by_field_name("value")
                        if fn:
                            val_expr = self._build_expr(fv) if fv else self._build_expr(fn)
                            inits.append(
                                StructFieldInit(
                                    field_name=self.get_text(fn),
                                    value=val_expr
                                )
                            )
            return StructInitExpr(
                struct_name=self.get_text(name_node) if name_node else "Struct",
                fields=inits
            )

        if ntype in ("tuple_expression", "parenthesized_expression"):
            children = [c for c in node.children if get_node_type(c) not in ("(", ")", ",")]
            if len(children) > 1 or ntype == "tuple_expression":
                tuple_inits: List[StructFieldInit] = []
                for elem_idx, child in enumerate(children):
                    tuple_inits.append(
                        StructFieldInit(
                            field_name=str(elem_idx),
                            value=self._build_expr(child)
                        )
                    )
                return StructInitExpr(
                    struct_name=".",
                    fields=tuple_inits
                )
            elif len(children) == 1:
                return self._build_expr(children[0])

        if ntype == "closure_expression":
            params_node = node.child_by_field_name("parameters")
            body_node = node.child_by_field_name("body")
            if not body_node and len(node.children) > 1:
                body_node = node.children[-1]

            closure_params: List[Param] = []
            if params_node:
                for child in params_node.children:
                    c_type = get_node_type(child)
                    if c_type not in ("|", ","):
                        if c_type == "parameter":
                            pn = child.child_by_field_name("pattern")
                            pt = child.child_by_field_name("type")
                            p_name = self.get_text(pn) if pn else "arg"
                            p_name = p_name.replace("(", "").replace(")", "").replace(" ", "_").replace("&", "").strip()
                            closure_params.append(
                                Param(
                                    name=p_name if p_name else "arg",
                                    param_type=self._build_type(pt) if pt else TypeNode(name="anytype")
                                )
                            )
                        else:
                            p_name = self.get_text(child).replace("(", "").replace(")", "").replace(" ", "_").replace("&", "").strip()
                            closure_params.append(
                                Param(
                                    name=p_name if p_name else "arg",
                                    param_type=TypeNode(name="anytype")
                                )
                            )

            body_expr = self._build_expr(body_node) if body_node else BlockExpr()
            return ClosureExpr(params=closure_params, body=body_expr)

        if ntype == "macro_invocation":
            macro_node = node.children[0] if node.children else None
            macro_name = self.get_text(macro_node).replace("!", "").strip() if macro_node else "macro"
            raw_args = self.get_text(node)
            return MacroCallExpr(macro_name=macro_name, raw_args_str=raw_args)

        if ntype == "if_expression":
            cond_node = node.child_by_field_name("condition")
            conseq_node = node.child_by_field_name("consequence")
            alt_node = node.child_by_field_name("alternative")

            cond = self._build_expr(cond_node) if cond_node else LiteralExpr("true", "bool")
            then_block = self._build_block(conseq_node) if conseq_node else BlockExpr()
            else_block: Optional[Union[BlockExpr, IfExpr]] = None

            if alt_node:
                alt_type = get_node_type(alt_node)
                if alt_type == "if_expression":
                    else_block = self._build_expr(alt_node)  # type: ignore
                elif alt_type == "block":
                    else_block = self._build_block(alt_node)

            return IfExpr(condition=cond, then_block=then_block, else_block=else_block)

        if ntype in ("while_expression", "for_expression", "loop_expression"):
            kind_map = {
                "while_expression": "while",
                "for_expression": "for",
                "loop_expression": "loop"
            }
            body_node = node.child_by_field_name("body")
            body = self._build_block(body_node) if body_node else BlockExpr()

            cond_expr: Optional[Expr] = None
            var_name: Optional[str] = None
            iterable: Optional[Expr] = None

            if ntype == "while_expression":
                c = node.child_by_field_name("condition")
                cond_expr = self._build_expr(c) if c else None
            elif ntype == "for_expression":
                p = node.child_by_field_name("pattern")
                var_name = self.get_text(p) if p else "i"
                v = node.child_by_field_name("value")
                iterable = self._build_expr(v) if v else None

            return LoopExpr(
                loop_kind=kind_map[ntype],
                condition=cond_expr,
                var_name=var_name,
                iterable=iterable,
                body=body
            )

        if ntype == "return_expression":
            val_node = node.children[1] if len(node.children) > 1 else None
            return ReturnExpr(value=self._build_expr(val_node) if val_node else None)

        if ntype == "block":
            return self._build_block(node)

        # Fallback expression wrapper
        return IdentifierExpr(name=self.get_text(node))

    def _is_expr_node(self, node: tree_sitter.Node) -> bool:
        """Check if node represents an expression rather than statement."""
        ntype = get_node_type(node)
        return ntype.endswith("_expression") or ntype in (
            "identifier",
            "integer_literal",
            "float_literal",
            "string_literal",
            "boolean_literal",
            "call_expression",
            "macro_invocation"
        )

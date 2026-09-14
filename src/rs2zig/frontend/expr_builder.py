"""
Expression Builder for rs2zig Frontend.

Constructs IR expression nodes from tree-sitter Rust CST nodes.
"""

from typing import List, Optional, Union, Any
import tree_sitter

from rs2zig.ir.nodes import (
    Expr, LiteralExpr, IdentifierExpr, BinaryExpr, UnaryExpr, CallExpr,
    FieldAccessExpr, StructInitExpr, StructFieldInit, MacroCallExpr, ReturnExpr,
    IfExpr, LoopExpr, MatchExpr, MatchArm, TryExpr, OptionalUnwrapExpr,
    ClosureExpr, BreakExpr, ContinueExpr, BlockExpr, Param, TypeNode
)
from rs2zig.frontend.decl_builder import get_node_type, build_type
from rs2zig.lowering.stdlib_map import map_type


def build_expr(builder: Any, node: tree_sitter.Node) -> Expr:
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
        return LiteralExpr(value=builder.get_text(node), kind=k_map.get(ntype, "int"))

    if ntype == "identifier":
        return IdentifierExpr(name=builder.get_text(node))

    if ntype == "let_condition":
        pat_node = node.child_by_field_name("pattern")
        val_node = node.child_by_field_name("value")
        pat_text = builder.get_text(pat_node) if pat_node else "_"
        val_expr = build_expr(builder, val_node) if val_node else LiteralExpr("null", "int")
        return BinaryExpr(left=IdentifierExpr(f"let {pat_text}"), op="=", right=val_expr)

    if ntype == "binary_expression":
        left_node = node.child_by_field_name("left")
        op_node = node.child_by_field_name("operator")
        right_node = node.child_by_field_name("right")
        return BinaryExpr(
            left=build_expr(builder, left_node) if left_node else LiteralExpr("0", "int"),
            op=builder.get_text(op_node) if op_node else "+",
            right=build_expr(builder, right_node) if right_node else LiteralExpr("0", "int")
        )

    if ntype in ("assignment_expression", "compound_assignment_expr"):
        left_node = node.child_by_field_name("left") or (node.children[0] if len(node.children) > 2 else None)
        op_node = node.child_by_field_name("operator") or (node.children[1] if len(node.children) > 2 else None)
        right_node = node.child_by_field_name("right") or (node.children[2] if len(node.children) > 2 else None)
        return BinaryExpr(
            left=build_expr(builder, left_node) if left_node else IdentifierExpr("lhs"),
            op=builder.get_text(op_node) if op_node else "=",
            right=build_expr(builder, right_node) if right_node else LiteralExpr("0", "int")
        )

    if ntype in ("unary_expression", "reference_expression"):
        op_node = node.child_by_field_name("operator") or (node.children[0] if len(node.children) > 0 else None)
        arg_node = node.child_by_field_name("argument") or node.child_by_field_name("value")
        if not arg_node and len(node.children) > 1:
            non_op_children = [c for c in node.children if get_node_type(c) not in ("&", "mut", "mutable_specifier", "-", "!")]
            arg_node = non_op_children[-1] if non_op_children else node.children[-1]
        op_str = "&" if ntype == "reference_expression" else (builder.get_text(op_node) if op_node else "-")
        return UnaryExpr(
            op=op_str,
            operand=build_expr(builder, arg_node) if arg_node else LiteralExpr("0", "int")
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
        fn_expr = build_expr(builder, fn_node) if fn_node else IdentifierExpr("unknown_generic_fn")
        type_args_str = builder.get_text(type_args_node) if type_args_node else ""
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
        val_expr = build_expr(builder, val_node) if val_node else IdentifierExpr("val")
        target_type_str = map_type(build_type(builder, type_node)) if type_node else "anytype"
        if target_type_str.startswith("*") or target_type_str in ("_", "*mut _", "*const _"):
            return CallExpr(callee=IdentifierExpr("@ptrCast"), args=[val_expr])
        return CallExpr(callee=IdentifierExpr("@as"), args=[IdentifierExpr(target_type_str), val_expr])

    if ntype == "unsafe_block":
        block_node = node.child_by_field_name("block") or (node.children[1] if len(node.children) > 1 else None)
        return builder._build_block(block_node) if block_node else BlockExpr()

    if ntype == "await_expression":
        operand_node = node.children[0] if node.children else None
        return build_expr(builder, operand_node) if operand_node else IdentifierExpr("future")

    if ntype == "try_expression":
        operand_node = node.children[0] if node.children else None
        return TryExpr(operand=build_expr(builder, operand_node) if operand_node else IdentifierExpr("res"))

    if ntype == "range_expression":
        left_node = node.child_by_field_name("left") or (node.children[0] if len(node.children) > 1 and get_node_type(node.children[0]) != ".." else None)
        right_node = node.child_by_field_name("right") or (node.children[-1] if len(node.children) > 1 and get_node_type(node.children[-1]) != ".." else None)
        left_expr = build_expr(builder, left_node) if left_node else LiteralExpr("0", "int")
        right_expr = build_expr(builder, right_node) if right_node else IdentifierExpr("len")
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
                                pattern=builder.get_text(pat_node),
                                body=build_expr(builder, arm_val_node)
                            )
                        )

        return MatchExpr(
            target=build_expr(builder, val_node) if val_node else IdentifierExpr("val"),
            arms=arms
        )

    if ntype == "call_expression":
        fn_node = node.child_by_field_name("function")
        args_node = node.child_by_field_name("arguments")
        callee_text = builder.get_text(fn_node) if fn_node else ""

        if fn_node and (get_node_type(fn_node) == "break_expression" or callee_text == "break"):
            arg_expr = None
            if args_node:
                non_delim = [c for c in args_node.children if get_node_type(c) not in ("(", ")", ",", "comment")]
                if non_delim:
                    arg_expr = build_expr(builder, non_delim[0])
            return BreakExpr(value=arg_expr)

        if callee_text.endswith(".unwrap"):
            target_expr = build_expr(builder, fn_node.child_by_field_name("value")) if fn_node and fn_node.type == "field_expression" else IdentifierExpr("opt")
            return OptionalUnwrapExpr(operand=target_expr)

        args: List[Expr] = []
        if args_node:
            for child in args_node.children:
                if get_node_type(child) not in ("(", ")", ",", "comment", "line_comment", "block_comment"):
                    args.append(build_expr(builder, child))

        return CallExpr(
            callee=build_expr(builder, fn_node) if fn_node else IdentifierExpr("unknown_fn"),
            args=args
        )

    if ntype == "array_expression":
        text = builder.get_text(node)
        if ";" in text:
            inner = text.strip("[]")
            parts = inner.split(";", 1)
            val_clean = parts[0].strip().replace("_u8", "").replace("u8", "")
            count_clean = parts[1].strip()
            return LiteralExpr(value=f"([_]u8{{{val_clean}}} ** {count_clean})", kind="array")
        else:
            elem_nodes = [c for c in node.children if get_node_type(c) not in ("[", "]", ",", "line_comment", "block_comment", "comment")]
            if elem_nodes:
                inits = [
                    StructFieldInit(field_name=str(idx), value=build_expr(builder, c))
                    for idx, c in enumerate(elem_nodes)
                ]
                return StructInitExpr(struct_name=".", fields=inits)

    if ntype == "field_expression":
        val_node = node.child_by_field_name("value")
        field_node = node.child_by_field_name("field")
        return FieldAccessExpr(
            target=build_expr(builder, val_node) if val_node else IdentifierExpr("obj"),
            field_name=builder.get_text(field_node) if field_node else "field"
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
                        val_expr = build_expr(builder, fv) if fv else build_expr(builder, fn)
                        inits.append(
                            StructFieldInit(
                                field_name=builder.get_text(fn),
                                value=val_expr
                            )
                        )
        return StructInitExpr(
            struct_name=builder.get_text(name_node) if name_node else "Struct",
            fields=inits
        )

    if ntype in ("tuple_expression", "parenthesized_expression"):
        children = [c for c in node.children if get_node_type(c) not in ("(", ")", ",", "line_comment", "block_comment", "comment")]
        if len(children) > 1 or ntype == "tuple_expression":
            tuple_inits: List[StructFieldInit] = []
            for elem_idx, child in enumerate(children):
                tuple_inits.append(
                    StructFieldInit(
                        field_name=str(elem_idx),
                        value=build_expr(builder, child)
                    )
                )
            return StructInitExpr(
                struct_name=".",
                fields=tuple_inits
            )
        elif len(children) == 1:
            return build_expr(builder, children[0])

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
                        p_name = builder.get_text(pn) if pn else "arg"
                        p_name = p_name.replace("(", "").replace(")", "").replace(" ", "_").replace("&", "").strip()
                        closure_params.append(
                            Param(
                                name=p_name if p_name else "arg",
                                param_type=build_type(builder, pt) if pt else TypeNode(name="anytype")
                            )
                        )
                    else:
                        p_name = builder.get_text(child).replace("(", "").replace(")", "").replace(" ", "_").replace("&", "").strip()
                        closure_params.append(
                            Param(
                                name=p_name if p_name else "arg",
                                param_type=TypeNode(name="anytype")
                            )
                        )

        body_expr = build_expr(builder, body_node) if body_node else BlockExpr()
        return ClosureExpr(params=closure_params, body=body_expr)

    if ntype in ("async_expression", "async_block", "unsafe_block"):
        body_node = node.child_by_field_name("body")
        if not body_node and len(node.children) > 0:
            body_candidates = [c for c in node.children if get_node_type(c) in ("block", "expression") or get_node_type(c).endswith("_expression") or get_node_type(c).endswith("_block")]
            body_node = body_candidates[-1] if body_candidates else node.children[-1]
        return build_expr(builder, body_node) if body_node else BlockExpr()

    if ntype == "await_expression":
        val_node = node.children[0] if node.children else None
        return build_expr(builder, val_node) if val_node else IdentifierExpr(name="void")

    if ntype == "try_expression":
        val_node = node.children[0] if node.children else None
        return build_expr(builder, val_node) if val_node else IdentifierExpr(name="void")

    if ntype == "macro_invocation":
        macro_node = node.children[0] if node.children else None
        macro_name = builder.get_text(macro_node).replace("!", "").strip() if macro_node else "macro"
        raw_args = builder.get_text(node)
        return MacroCallExpr(macro_name=macro_name, raw_args_str=raw_args)

    if ntype == "if_expression":
        cond_node = node.child_by_field_name("condition")
        conseq_node = node.child_by_field_name("consequence")
        alt_node = node.child_by_field_name("alternative")

        cond = build_expr(builder, cond_node) if cond_node else LiteralExpr("true", "bool")
        then_block = builder._build_block(conseq_node) if conseq_node else BlockExpr()
        else_block: Optional[Union[BlockExpr, IfExpr]] = None

        if alt_node:
            alt_type = get_node_type(alt_node)
            if alt_type == "if_expression":
                else_block = build_expr(builder, alt_node)  # type: ignore
            elif alt_type == "block":
                else_block = builder._build_block(alt_node)

        return IfExpr(condition=cond, then_block=then_block, else_block=else_block)

    if ntype in ("while_expression", "for_expression", "loop_expression"):
        kind_map = {
            "while_expression": "while",
            "for_expression": "for",
            "loop_expression": "loop"
        }
        body_node = node.child_by_field_name("body")
        body = builder._build_block(body_node) if body_node else BlockExpr()

        cond_expr: Optional[Expr] = None
        var_name: Optional[str] = None
        iterable: Optional[Expr] = None

        if ntype == "while_expression":
            c = node.child_by_field_name("condition")
            cond_expr = build_expr(builder, c) if c else None
        elif ntype == "for_expression":
            p = node.child_by_field_name("pattern")
            var_name = builder.get_text(p) if p else "i"
            v = node.child_by_field_name("value")
            iterable = build_expr(builder, v) if v else None

        return LoopExpr(
            loop_kind=kind_map[ntype],
            condition=cond_expr,
            var_name=var_name,
            iterable=iterable,
            body=body
        )

    if ntype == "break_expression":
        val_node = None
        label = None
        for child in node.children[1:]:
            ctype = get_node_type(child)
            if ctype == "loop_label" or (ctype == "label" and builder.get_text(child).startswith("'")):
                label = builder.get_text(child)
            elif ctype not in (",", ";"):
                val_node = child
        return BreakExpr(
            value=build_expr(builder, val_node) if val_node else None,
            label=label
        )

    if ntype == "continue_expression":
        label = None
        for child in node.children[1:]:
            ctype = get_node_type(child)
            if ctype == "loop_label" or (ctype == "label" and builder.get_text(child).startswith("'")):
                label = builder.get_text(child)
        return ContinueExpr(label=label)

    if ntype == "return_expression":
        val_node = node.children[1] if len(node.children) > 1 else None
        return ReturnExpr(value=build_expr(builder, val_node) if val_node else None)

    if ntype == "block":
        return builder._build_block(node)

    if ntype in ("line_comment", "block_comment", "comment"):
        return LiteralExpr(value="", kind="comment")

    # Fallback expression wrapper
    return IdentifierExpr(name=builder.get_text(node))


def is_expr_node(node: tree_sitter.Node) -> bool:
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

"""
Declaration Builder for rs2zig Frontend.

Constructs IR declaration nodes from tree-sitter Rust CST nodes.
"""

from typing import List, Optional, Any
import tree_sitter

from rs2zig.ir.nodes import (
    ConstDecl, StructDecl, FieldDecl, EnumDecl, EnumVariant, EnumVariantField,
    TraitDecl, GenericParam, Attribute, ImplBlock, FnDecl, Param, TypeNode,
    BlockExpr, LiteralExpr
)
from rs2zig.lowering.stdlib_map import _split_angle_brackets, _split_top_level_commas


def get_node_type(node: tree_sitter.Node) -> str:
    """Safely get string node type."""
    return getattr(node, "type", getattr(node, "kind", ""))


def build_const(builder: Any, node: tree_sitter.Node) -> ConstDecl:
    """Build ConstDecl from const_item or static_item node."""
    is_pub = any(get_node_type(c) == "visibility_modifier" for c in node.children)
    is_static = get_node_type(node) == "static_item"
    name_node = node.child_by_field_name("name")
    type_node = node.child_by_field_name("type")
    val_node = node.child_by_field_name("value")

    name = builder.get_text(name_node) if name_node else "CONST_VAL"
    ctype = build_type(builder, type_node) if type_node else TypeNode(name="anytype")
    val = builder._build_expr(val_node) if val_node else LiteralExpr(value="0", kind="int")

    return ConstDecl(name=name, const_type=ctype, value=val, is_pub=is_pub, is_static=is_static)


def build_struct(builder: Any, node: tree_sitter.Node) -> StructDecl:
    """Build StructDecl from struct_item node."""
    name_node = node.child_by_field_name("name")
    struct_name = builder.get_text(name_node) if name_node else "UnknownStruct"
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
                            name=builder.get_text(fname_node),
                            field_type=build_type(builder, ftype_node),
                            is_pub=f_is_pub
                        )
                    )

    generic_params: List[GenericParam] = []
    type_params = node.child_by_field_name("type_parameters")
    if type_params:
        for child in type_params.children:
            if get_node_type(child) in ("type_parameter", "constrained_type_parameter", "type_identifier"):
                gname = builder.get_text(child).split("=")[0].split(":")[0].strip()
                if gname not in ("<", ">", ","):
                    generic_params.append(GenericParam(name=gname))

    return StructDecl(name=struct_name, fields=fields, is_pub=is_pub, generic_params=generic_params)


def build_enum(builder: Any, node: tree_sitter.Node) -> EnumDecl:
    """Build EnumDecl from enum_item node."""
    name_node = node.child_by_field_name("name")
    enum_name = builder.get_text(name_node) if name_node else "UnknownEnum"
    is_pub = any(get_node_type(child) == "visibility_modifier" for child in node.children)

    variants: List[EnumVariant] = []
    body_node = node.child_by_field_name("body")
    if body_node:
        for child in body_node.children:
            if get_node_type(child) == "enum_variant":
                variants.append(build_enum_variant(builder, child))

    return EnumDecl(name=enum_name, variants=variants, is_pub=is_pub)


def build_enum_variant(builder: Any, node: tree_sitter.Node) -> EnumVariant:
    """Build EnumVariant from enum_variant node."""
    name_node = node.child_by_field_name("name")
    vname = builder.get_text(name_node) if name_node else builder.get_text(node).split("{")[0].split("(")[0].strip()

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
                            name=builder.get_text(fn) if fn else None,
                            field_type=build_type(builder, ft)
                        )
                    )
            elif get_node_type(child) == "tuple_field":
                ft = child.child_by_field_name("type") or child
                variant_fields.append(
                    EnumVariantField(name=None, field_type=build_type(builder, ft))
                )

    return EnumVariant(name=vname, fields=variant_fields)


def build_trait(builder: Any, node: tree_sitter.Node) -> TraitDecl:
    """Build TraitDecl from trait_item node."""
    name_node = node.child_by_field_name("name")
    trait_name = builder.get_text(name_node) if name_node else "UnknownTrait"
    is_pub = any(get_node_type(child) == "visibility_modifier" for child in node.children)
    methods: List[FnDecl] = []

    body_node = node.child_by_field_name("body")
    if body_node:
        for child in body_node.children:
            if get_node_type(child) in ("function_item", "function_signature_item"):
                methods.append(build_function(builder, child))

    return TraitDecl(name=trait_name, methods=methods, is_pub=is_pub)


def build_impl(builder: Any, node: tree_sitter.Node) -> ImplBlock:
    """Build ImplBlock from impl_item node."""
    type_node = node.child_by_field_name("type")
    trait_node = node.child_by_field_name("trait")

    struct_name = builder.get_text(type_node) if type_node else "UnknownType"
    trait_name = builder.get_text(trait_node) if trait_node else None
    methods: List[FnDecl] = []

    body = node.child_by_field_name("body")
    if body:
        for child in body.children:
            if get_node_type(child) in ("function_item", "function_signature_item"):
                methods.append(build_function(builder, child))

    return ImplBlock(struct_name=struct_name, trait_name=trait_name, methods=methods)


def build_function(builder: Any, node: tree_sitter.Node) -> FnDecl:
    """Build FnDecl from function_item node."""
    name_node = node.child_by_field_name("name")
    func_name = builder.get_text(name_node) if name_node else "unnamed_fn"
    is_pub = any(get_node_type(child) == "visibility_modifier" for child in node.children)

    generic_params: List[GenericParam] = []
    type_params = node.child_by_field_name("type_parameters")
    if type_params:
        for child in type_params.children:
            if get_node_type(child) in ("type_parameter", "constrained_type_parameter", "type_identifier"):
                gname = builder.get_text(child).split("=")[0].split(":")[0].strip()
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
                            name=builder.get_text(pattern_node),
                            param_type=build_type(builder, type_node)
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
    return_type = build_type(builder, ret_type_node) if ret_type_node else None

    body_node = node.child_by_field_name("body")
    body = builder._build_block(body_node) if body_node else None

    return FnDecl(
        name=func_name,
        params=params,
        return_type=return_type,
        body=body,
        is_pub=is_pub,
        generic_params=generic_params
    )


def build_type(builder: Any, node: Optional[tree_sitter.Node]) -> TypeNode:
    """Build TypeNode from type syntax node."""
    if not node:
        return TypeNode(name="void")

    text = builder.get_text(node).strip()
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
        is_arr_slice = clean_text.startswith("[") and clean_text.endswith("]")
        split_res = _split_angle_brackets(clean_text) if (not is_arr_slice and not (clean_text.startswith("(") and clean_text.endswith(")"))) else None
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

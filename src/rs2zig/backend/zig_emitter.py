"""
Zig Source Code Emitter for rs2zig.

Renders IR nodes into standard Zig source code (.zig).
"""

import os
import re
from typing import List, Optional, Set
from rs2zig.ir.nodes import SourceFile, StructDecl, EnumDecl, TraitDecl, FnDecl, BlockExpr, Stmt, Expr
from rs2zig.lowering.stdlib_map import map_type
from rs2zig.backend.emitter_constants import ZIG_KEYWORDS_AND_PRIMITIVES
from rs2zig.backend.decl_emitter import emit_trait_decl, emit_enum_decl, emit_struct_decl, emit_function_decl
from rs2zig.backend.fallback_emitter import generate_fallback_headers
from rs2zig.backend.stmt_emitter import emit_stmt, emit_block_lines
from rs2zig.backend.expr_emitter import emit_expr


class ZigEmitter:
    """Walks rs2zig IR nodes and emits formatted Zig source code."""

    def __init__(self, indent_str: str = "    ") -> None:
        """Initialize emitter with specified indentation."""
        self.indent_str = indent_str
        self.current_indent = 0
        self.requires_bevy_runtime = False
        self.imported_modules: Set[str] = set()
        self.tmp_var_counter = 0

    def emit_source_file(self, sf: SourceFile, file_path: Optional[str] = None) -> str:
        """Emit complete Zig source file string from SourceFile node."""
        self.imported_modules.clear()
        impl_map = {impl.struct_name: impl.methods for impl in sf.impls}

        body_lines: List[str] = []

        for c in sf.constants:
            vis = "pub " if c.is_pub else ""
            type_str = map_type(c.const_type)
            val_str = self._emit_expr(c.value).rstrip(";").strip()
            body_lines.append(f"{vis}const {c.name}: {type_str} = {val_str};")
            body_lines.append("")

        for trait in sf.traits:
            body_lines.append(self._emit_trait(trait))
            body_lines.append("")

        for enum_decl in sf.enums:
            body_lines.append(self._emit_enum(enum_decl))
            body_lines.append("")

        for struct in sf.structs:
            methods = impl_map.get(struct.name, [])
            body_lines.append(self._emit_struct(struct, methods))
            body_lines.append("")

        for fn in sf.functions:
            body_lines.append(self._emit_function(fn))
            body_lines.append("")

        header_lines: List[str] = ['const std = @import("std");']

        if self.requires_bevy_runtime:
            header_lines.extend([
                'const bevy_ecs = @import("bevy_ecs_runtime.zig");',
                'const channel = bevy_ecs.channel;',
                'const stdin = bevy_ecs.stdin;',
                'const String = []u8;',
                'const IpAddr = []u8;',
                'const UdpSocket = bevy_ecs.UdpSocket;',
                'const aok_core = @import("aok_core");'
            ])
            if not any(fn.name == "create_app" for fn in sf.functions):
                header_lines.append('const create_app = aok_core.create_app;')

        out_dir = os.path.dirname(file_path) if file_path else ""
        top_level_names = {c.name for c in sf.constants} | {s.name for s in sf.structs} | {e.name for e in sf.enums} | {t.name for t in sf.traits} | {f.name for f in sf.functions}
        all_declared_names = set(top_level_names)
        for s in sf.structs:
            all_declared_names.update(f.name for f in s.fields)
        for e in sf.enums:
            all_declared_names.update(v.name for v in e.variants)
        for impl in sf.impls:
            all_declared_names.update(m.name for m in impl.methods)

        for mod_name in sorted(set(self.imported_modules) | set(getattr(sf, "imports", []))):
            if mod_name.isidentifier() and not mod_name.startswith("const") and mod_name not in ("self", "super", "crate", "std", "bevy", "bevy_ecs", "aok_core", "create_app", "serde"):
                if mod_name in all_declared_names:
                    continue
                clean_mod_name = f'@"{mod_name}"' if mod_name in ZIG_KEYWORDS_AND_PRIMITIVES else mod_name
                if mod_name == "aok":
                    header_lines.append('const aok = aok_core;')
                elif mod_name == "core":
                    header_lines.append('pub const core = std;')
                elif mod_name == "libc":
                    header_lines.append('pub const libc = std.c;')
                elif mod_name == "c_void":
                    header_lines.append('pub const c_void = anyopaque;')
                elif out_dir and os.path.exists(os.path.join(out_dir, f"{mod_name}.zig")):
                    header_lines.append(f'const {clean_mod_name} = @import("{mod_name}.zig");')
                else:
                    header_lines.append(f'pub const {clean_mod_name} = *anyopaque;')

        body_text = "\n".join(body_lines)
        clean_body = re.sub(r'"[^"]*"', '""', body_text)
        clean_body = re.sub(r'//.*', '', clean_body)

        generate_fallback_headers(clean_body, all_declared_names, self.imported_modules, header_lines)

        header_lines.append("")
        all_lines = header_lines + body_lines

        return "\n".join(all_lines).strip() + "\n"

    def _indent(self) -> str:
        """Get current indentation string."""
        return self.indent_str * self.current_indent

    def _emit_trait(self, trait: TraitDecl) -> str:
        """Emit Zig interface definition for a trait."""
        return emit_trait_decl(trait)

    def _emit_enum(self, enum_decl: EnumDecl) -> str:
        """Emit Zig enum or tagged union definition."""
        return emit_enum_decl(
            enum_decl, self._indent,
            lambda: setattr(self, "current_indent", self.current_indent + 1),
            lambda: setattr(self, "current_indent", self.current_indent - 1)
        )

    def _emit_struct(self, struct: StructDecl, methods: List[FnDecl]) -> str:
        """Emit Zig struct definition including any impl methods."""
        return emit_struct_decl(struct, methods, self)

    def _emit_function(self, fn: FnDecl, parent_struct_name: Optional[str] = None) -> str:
        """Emit Zig function or method definition."""
        return emit_function_decl(fn, self, parent_struct_name)

    def _emit_block_lines(self, block: BlockExpr) -> List[str]:
        """Emit list of indented statement strings inside a block."""
        return emit_block_lines(block, self)

    def _emit_stmt(self, stmt: Stmt) -> str:
        """Emit single statement string without leading indent."""
        return emit_stmt(stmt, self)

    def _emit_expr(self, expr: Expr) -> str:
        """Emit expression string."""
        return emit_expr(expr, self)

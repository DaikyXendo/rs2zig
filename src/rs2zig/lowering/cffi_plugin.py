"""
C-FFI & Unsafe Pointer Lowering Plugin for rs2zig.

Handles raw pointer types (*const T, *mut T), unsafe block transpilation, and extern "C" functions for native Zig interop.
"""

import logging
from typing import Optional
from rs2zig.ir.nodes import SourceFile, TypeNode, FnDecl
from rs2zig.lowering.plugin_api import LibraryLoweringPlugin

logger = logging.getLogger("rs2zig.lowering.cffi_plugin")


class CFFIPlugin(LibraryLoweringPlugin):
    """Lowering plugin for C-FFI and raw pointers."""

    def crate_name(self) -> str:
        """Return crate name."""
        return "cffi"

    def lower_type(self, type_node: TypeNode) -> Optional[TypeNode]:
        """Lower raw pointer types to Zig C-interop types.

        Args:
            type_node: Input TypeNode.

        Returns:
            Transformed TypeNode or None.
        """
        if type_node.is_raw_pointer:
            name = type_node.name.strip()
            if name.startswith("*const "):
                inner = name[7:].strip()
                return TypeNode(name=f"[*c]const {inner}")
            elif name.startswith("*mut "):
                inner = name[5:].strip()
                return TypeNode(name=f"[*c]{inner}")

        return None

    def lower_source_file(self, sf: SourceFile) -> bool:
        """Traverse SourceFile AST and lower C-FFI pointer types.

        Args:
            sf: SourceFile AST node.

        Returns:
            False as C-FFI uses built-in Zig language features.
        """
        for fn in sf.functions:
            for param in fn.params:
                new_t = self.lower_type(param.param_type)
                if new_t:
                    param.param_type = new_t

            if fn.return_type:
                new_t = self.lower_type(fn.return_type)
                if new_t:
                    fn.return_type = new_t

        return False

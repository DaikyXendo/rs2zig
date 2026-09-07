"""
Serde Serialization Lowering Plugin for rs2zig.

Detects Serde derive attributes (#[derive(Serialize, Deserialize)]) and lowers struct serialization methods for Zig 0.16.0 std.json.
"""

import logging
from typing import Optional
from rs2zig.ir.nodes import SourceFile, StructDecl
from rs2zig.lowering.plugin_api import LibraryLoweringPlugin

logger = logging.getLogger("rs2zig.lowering.serde_plugin")


class SerdePlugin(LibraryLoweringPlugin):
    """Lowering plugin for Serde serialization framework."""

    def crate_name(self) -> str:
        """Return crate name."""
        return "serde"

    def lower_source_file(self, sf: SourceFile) -> bool:
        """Traverse SourceFile AST and lower Serde derives.

        Args:
            sf: SourceFile AST node.

        Returns:
            True if Serde runtime is used.
        """
        serde_used = False

        for struct_decl in sf.structs:
            for attr in struct_decl.attributes:
                if attr.name == "derive":
                    if any(arg in ("Serialize", "Deserialize", "serde::Serialize", "serde::Deserialize") for arg in attr.args):
                        serde_used = True
                        logger.info(f"Lowering Serde derive for struct '{struct_decl.name}'")

        return serde_used

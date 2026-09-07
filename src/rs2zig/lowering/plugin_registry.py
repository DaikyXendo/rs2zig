"""
Global Plugin Registry for rs2zig Library Lowering Architecture.

Manages active lowering plugins and executes them sequentially on IR ASTs.
"""

import logging
from typing import List
from rs2zig.ir.nodes import SourceFile
from rs2zig.lowering.plugin_api import LibraryLoweringPlugin

logger = logging.getLogger("rs2zig.lowering.plugin_registry")


class PluginRegistry:
    """Registry managing active library lowering plugins."""

    def __init__(self) -> None:
        """Initialize empty plugin registry."""
        self.plugins: List[LibraryLoweringPlugin] = []

    def register_plugin(self, plugin: LibraryLoweringPlugin) -> None:
        """Register a new library lowering plugin.

        Args:
            plugin: LibraryLoweringPlugin instance to add.
        """
        self.plugins.append(plugin)
        logger.debug(f"Registered lowering plugin: {plugin.crate_name()}")

    def run_lowering_passes(self, sf: SourceFile) -> List[str]:
        """Run all registered lowering plugins on SourceFile AST.

        Args:
            sf: SourceFile AST node to transform.

        Returns:
            List of required runtime module names (e.g. ['bevy_ecs']).
        """
        required_runtimes: List[str] = []

        for plugin in self.plugins:
            try:
                requires_runtime = plugin.lower_source_file(sf)
                if requires_runtime:
                    required_runtimes.append(plugin.crate_name())
            except Exception as e:
                logger.warning(f"Plugin {plugin.crate_name()} failed on source file: {e}")

        return required_runtimes

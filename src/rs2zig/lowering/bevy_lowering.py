"""
Bevy Engine API Lowering Pass for rs2zig.

Re-exports BevyPlugin for backwards compatibility.
"""

from rs2zig.lowering.bevy_plugin import BevyPlugin as BevyLoweringPass

__all__ = ["BevyLoweringPass"]

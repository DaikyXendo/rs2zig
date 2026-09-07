#!/usr/bin/env python3
"""
rs2zig Main Entry Point.
Rust to Zig source code converter in Python.
"""

import sys
import logging
from rs2zig.cli import main as cli_main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("rs2zig")

def main() -> None:
    """Main application entry point."""
    cli_main()

if __name__ == "__main__":
    main()

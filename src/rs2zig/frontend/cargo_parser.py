"""
Cargo.toml Parser for rs2zig.

Parses Cargo.toml files to extract package metadata, dependencies, and workspace structure.
"""

import os
import logging
import tomllib
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

logger = logging.getLogger("rs2zig.frontend.cargo_parser")


@dataclass
class CargoPackage:
    """Metadata for a Cargo package."""
    name: str
    version: str = "0.1.0"
    edition: str = "2021"


@dataclass
class CargoManifest:
    """Parsed representation of a Cargo.toml file."""
    package: CargoPackage
    dependencies: Dict[str, Union[str, Dict[str, Any]]] = field(default_factory=dict)
    workspace_members: List[str] = field(default_factory=list)


def parse_cargo_toml(cargo_path: str) -> Optional[CargoManifest]:
    """Parse Cargo.toml file and return CargoManifest dataclass.

    Args:
        cargo_path: Path to Cargo.toml file.

    Returns:
        CargoManifest object if parsed successfully, None otherwise.
    """
    if not os.path.exists(cargo_path):
        logger.debug(f"Cargo.toml not found at {cargo_path}")
        return None

    try:
        with open(cargo_path, "rb") as f:
            data = tomllib.load(f)

        pkg_data = data.get("package", {})
        pkg = CargoPackage(
            name=pkg_data.get("name", "app"),
            version=pkg_data.get("version", "0.1.0"),
            edition=pkg_data.get("edition", "2021")
        )

        deps = data.get("dependencies", {})
        ws_members = data.get("workspace", {}).get("members", [])

        manifest = CargoManifest(
            package=pkg,
            dependencies=deps,
            workspace_members=ws_members
        )
        logger.info(f"Successfully parsed Cargo.toml for package '{pkg.name}' with {len(deps)} dependencies.")
        return manifest
    except Exception as e:
        logger.warning(f"Failed to parse Cargo.toml at {cargo_path}: {e}")
        return None

"""Domain models for YAGSO manifest."""

from typing import List, Optional
from dataclasses import dataclass
from .submodule import SubmoduleDefinition


@dataclass
class Bom:
    """Represents the BOM.yaml bill of material structure."""
    submodules: List[SubmoduleDefinition]
    version: str = "1.1"

    @classmethod
    def from_dict(cls, data: dict) -> 'Manifest':
        """Create Manifest from dictionary representation."""
        version = data.get("version", "1.0")
        submodules = [SubmoduleDefinition.from_dict(s, True) for s in data.get("submodules", [])]

        # Set root paths for all submodules based on their hierarchy
        cls._set_root_paths(submodules)

        return cls(submodules=submodules, version=version)

    @classmethod
    def _set_root_paths(cls, subs, parent_path=""):
        """Recursively set root_path for submodules based on parent path."""

        for sub in subs:
            sub.root_path = parent_path + f"/{sub.path}" if parent_path else sub.path
            if sub.submodules:
                cls._set_root_paths(sub.submodules,
                                    f"{parent_path}/{sub.path}" if parent_path else sub.path)

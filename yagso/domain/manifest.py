"""Domain models for YAGSO manifest."""

from typing import List, Optional
from dataclasses import dataclass
from .submodule import SubmoduleDefinition


@dataclass
class Manifest:
    """Represents the yagso.yaml manifest structure."""
    submodules: List[SubmoduleDefinition]
    version: str = "1.0"

    def validate(self) -> None:
        """Validate manifest integrity."""
        if not self.submodules:
            raise ValueError("Manifest must contain at least one submodule")

        names = set()
        paths = set()
        for submodule in self.submodules:
            if not submodule.name:
                raise ValueError("Submodule name cannot be empty")
            if not submodule.path:
                raise ValueError("Submodule path cannot be empty")
            if not submodule.url:
                raise ValueError("Submodule URL cannot be empty")

            if submodule.name in names:
                raise ValueError(f"Duplicate submodule name: {submodule.name}")
            if submodule.path in paths:
                raise ValueError(f"Duplicate submodule path: {submodule.path}")

            names.add(submodule.name)
            paths.add(submodule.path)

    def get_submodule(self, name: str) -> Optional[SubmoduleDefinition]:
        """Retrieve submodule by name."""
        for submodule in self.submodules:
            if submodule.name == name:
                return submodule
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "version": self.version,
            "submodules": [sub.to_dict() for sub in self.submodules],
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Manifest':
        """Create Manifest from dictionary representation."""
        from .submodule import SubmoduleDefinition

        version = data.get("version", "1.0")
        submodules_data = data.get("submodules", [])

        submodules = []
        for sub_data in submodules_data:
            submodules.append(SubmoduleDefinition.from_dict(sub_data))

        return cls(submodules=submodules, version=version)

    @classmethod
    def from_dict(cls, data: dict) -> 'Manifest':
        """Create from dictionary representation."""
        return cls(
            version=data.get("version", "1.0"),
            submodules=[SubmoduleDefinition.from_dict(sub) for sub in data["submodules"]],
        )
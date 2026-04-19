"""Domain models for YAGSO manifest."""

from typing import List, Optional
from dataclasses import dataclass
from .submodule import SubmoduleDefinition


@dataclass
class Manifest:
    """Represents the yagso.yaml manifest structure."""
    submodules: List[SubmoduleDefinition]
    version: str = "1.0"

    def _collect(self, subs, root_paths) -> None:
        """Recursively collect and validate submodule root paths."""
        status = None

        for sub in subs:
            if not sub.name:
                raise ValueError("Submodule name cannot be empty")
            if not sub.path:
                raise ValueError("Submodule path cannot be empty")
            if not sub.url:
                raise ValueError("Submodule URL cannot be empty")
            if not sub.commit:
                raise ValueError("Submodule commit hash cannot be empty")
            if not sub.root_path:
                raise ValueError("Submodule root path cannot be empty")

            if sub.root_path in root_paths:
                raise ValueError(f"Duplicate submodule root path: {sub.root_path}")

            root_paths.add(sub.root_path)

            if getattr(sub, 'submodules', None):
                status = self._collect(sub.submodules, root_paths)

        return status

    def validate(self) -> None:
        """Validate manifest integrity."""
        if not self.submodules:
            raise ValueError("Manifest must contain at least one submodule")

        root_paths = set()
        self._collect(self.submodules, root_paths)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "version": self.version,
            "submodules": [sub.to_dict() for sub in self.submodules],
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Manifest':
        """Create Manifest from dictionary representation."""
        version = data.get("version", "1.0")
        submodules = [SubmoduleDefinition.from_dict(s) for s in data.get("submodules", [])]
        return cls(submodules=submodules, version=version)

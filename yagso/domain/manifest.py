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

        def _collect(subs):
            for sub in subs:
                if not sub.name:
                    raise ValueError("Submodule name cannot be empty")
                if not sub.path:
                    raise ValueError("Submodule path cannot be empty")
                if not sub.url:
                    raise ValueError("Submodule URL cannot be empty")

                if sub.name in names:
                    raise ValueError(f"Duplicate submodule name: {sub.name}")
                if sub.path in paths:
                    raise ValueError(f"Duplicate submodule path: {sub.path}")

                names.add(sub.name)
                paths.add(sub.path)

                if getattr(sub, 'submodules', None):
                    _collect(sub.submodules)

        _collect(self.submodules)

    def get_submodule(self, name: str) -> Optional[SubmoduleDefinition]:
        """Retrieve submodule by name."""
        def _find(subs):
            for s in subs:
                if s.name == name:
                    return s
                res = _find(s.submodules)
                if res:
                    return res
            return None

        return _find(self.submodules)

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

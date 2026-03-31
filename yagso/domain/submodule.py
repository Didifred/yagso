"""Domain model for submodule definitions."""

from typing import Optional
from dataclasses import dataclass


@dataclass
class SubmoduleDefinition:
    """Represents a single submodule configuration."""

    name: str
    path: str
    url: str
    branch: str
    commit: Optional[str] = None

    def __post_init__(self):
        """Validate the submodule definition after initialization."""
        if not self.name:
            raise ValueError("Submodule name cannot be empty")
        if not self.path:
            raise ValueError("Submodule path cannot be empty")
        if not self.url:
            raise ValueError("Submodule URL cannot be empty")
        if not self.branch:
            raise ValueError("Submodule branch cannot be empty")

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        result = {
            "name": self.name,
            "path": self.path,
            "url": self.url,
            "branch": self.branch,
        }
        if self.commit:
            result["commit"] = self.commit
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'SubmoduleDefinition':
        """Create SubmoduleDefinition from dictionary representation."""
        return cls(
            name=data["name"],
            path=data["path"],
            url=data["url"],
            branch=data["branch"],
            commit=data.get("commit")
        )
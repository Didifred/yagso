"""Domain model for submodule definitions."""

from typing import Optional
from dataclasses import dataclass


@dataclass
class SubmoduleDefinition:
    """Represents a single submodule configuration."""
    name : str
    path: str
    url: str
    """ The branch to track for this submodule. Defaults to None if not specified. """
    tracking_branch: Optional[str] = None
    """ The specific ref (branch /tag / commit hash) for this submodule. """
    ref: Optional[str] = None

    def __post_init__(self):
        """Validate the submodule definition after initialization."""
        if not self.path:
            raise ValueError("Submodule path cannot be empty")
        if not self.url:
            raise ValueError("Submodule URL cannot be empty")

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        result = {
            "name": self.name,
            "path": self.path,
            "url": self.url
        }
        if self.tracking_branch:
            result["tracking_branch"] = self.tracking_branch
        if self.ref:
            result["ref"] = self.ref    
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'SubmoduleDefinition':
        """Create SubmoduleDefinition from dictionary representation."""
        return cls(
            name=data["name"],
            path=data["path"],
            url=data["url"],
            tracking_branch=data.get("tracking_branch"),
            ref=data.get("ref")
        )
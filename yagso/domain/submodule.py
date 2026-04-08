"""Domain model for submodule definitions."""

from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class SubmoduleDefinition:
    """Represents a single submodule configuration."""
    root_path: str
    name: str
    path: str
    url: str
    commit: str
    """ The branch to track for this submodule. Defaults to None if not specified. """
    tracking_branch: Optional[str] = None
    """List of refs (branches/tags) that reference the recorded commit."""
    ref: Optional[List[str]] = None
    """ Child submodules nested under this submodule. """
    submodules: List['SubmoduleDefinition'] = field(default_factory=list)

    def __post_init__(self):
        """Validate the submodule definition after initialization."""
        if not self.root_path:
            raise ValueError("Root path of submodule cannot be empty")
        if not self.name:
            raise ValueError("Submodule name cannot be empty")
        if not self.path:
            raise ValueError("Submodule path cannot be empty")
        if not self.url:
            raise ValueError("Submodule URL cannot be empty")
        if not self.commit:
            raise ValueError("Submodule commit hash cannot be empty")

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        result = {
            "root_path": self.root_path,
            "name": self.name,
            "path": self.path,
            "url": self.url,
            "commit": self.commit,
        }
        if self.tracking_branch:
            result["tracking_branch"] = self.tracking_branch
        if self.ref:
            result["ref"] = list(self.ref)
        if self.submodules:
            result["submodules"] = [s.to_dict() for s in self.submodules]
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'SubmoduleDefinition':
        """Create SubmoduleDefinition from dictionary representation (including children)."""
        children = [cls.from_dict(c) for c in data.get("submodules", [])]
        commit = data.get("commit")
        if not commit:
            raise ValueError(
                f"Missing required 'commit' for submodule {
                    data.get(
                        'name', '<unknown>')}")
        return cls(
            root_path=data["root_path"],
            name=data["name"],
            path=data["path"],
            url=data["url"],
            commit=commit,
            tracking_branch=data.get("tracking_branch"),
            ref=data.get("ref"),
            submodules=children,
        )

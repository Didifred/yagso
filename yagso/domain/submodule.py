"""Domain model for submodule definitions."""

from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class SubmoduleDefinition:
    """Represents a single submodule configuration."""
    root_path: str
    commit: str
    path: str
    name: Optional[str] = None
    url: Optional[str] = None
    """ The branch to track for this submodule. Defaults to None if not specified. """
    tracking_branch: Optional[str] = None
    """List of refs (branches/tags) that reference the recorded commit."""
    ref: Optional[List[str]] = None
    """List of files that are part of this submodule. Defaults to None if not specified."""
    files: Optional[List[str]] = None
    """ Child submodules nested under this submodule. """
    submodules: List['SubmoduleDefinition'] = field(default_factory=list)

    def validate_manifest(self):
        """Validate the submodule definition for manifest (yagso.yaml)."""

        if not self.name:
            raise ValueError("Submodule name cannot be empty")
        if not self.path:
            raise ValueError("Submodule path cannot be empty")
        if not self.url:
            raise ValueError("Submodule URL cannot be empty")
        if not self.commit:
            raise ValueError("Submodule commit hash cannot be empty")

    def validate_bom(self):
        """Validate the submodule definition for BOM (BOM.yaml)."""

        if not self.path:
            raise ValueError("Submodule path cannot be empty")
        if not self.commit:
            raise ValueError("Submodule commit hash cannot be empty")

    def to_dict(self) -> dict:
        """Convert to dictionary representation for yaml."""
        result = {}

        if self.name:
            result["name"] = self.name

        result["path"] = self.path

        if self.url:
            result["url"] = self.url

        result["commit"] = self.commit

        if self.tracking_branch:
            result["tracking_branch"] = self.tracking_branch

        if self.ref:
            result["ref"] = list(self.ref)

        if self.files:
            result["files"] = list(self.files)

        if self.submodules:
            result["submodules"] = [s.to_dict() for s in self.submodules]

        return result

    @classmethod
    def from_dict(cls, data: dict, is_bom: bool) -> 'SubmoduleDefinition':
        """Create SubmoduleDefinition from dictionary representation (including children)."""
        children = [cls.from_dict(c, is_bom) for c in data.get("submodules", [])]

        s = cls(
            root_path="",
            commit=data["commit"],
            path=data["path"],
            name=data.get("name"),
            url=data.get("url"),
            tracking_branch=data.get("tracking_branch"),
            ref=data.get("ref"),
            files=data.get("files"),
            submodules=children,
        )

        if is_bom:
            s.validate_bom()
        else:
            s.validate_manifest()

        return s

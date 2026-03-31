"""Repository state domain model."""

from typing import List, Dict, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class RepositoryState:
    """Represents current repository state."""
    root_path: Path
    submodules: Dict[str, Dict[str, Any]]
    is_initialized: bool = False

    @property
    def submodule_paths(self) -> List[str]:
        """Get list of submodule paths."""
        return list(self.submodules.keys())

    @property
    def initialized_submodules(self) -> List[str]:
        """Get list of initialized submodule paths."""
        return [path for path, info in self.submodules.items()
                if info.get('initialized', False)]

    @property
    def uninitialized_submodules(self) -> List[str]:
        """Get list of uninitialized submodule paths."""
        return [path for path, info in self.submodules.items()
                if not info.get('initialized', False)]

    @classmethod
    def from_git_repo(cls, root_path: Path) -> 'RepositoryState':
        """Create RepositoryState from a Git repository path."""
        # This will be populated by GitOperations
        return cls(
            root_path=root_path,
            submodules={},
            is_initialized=False
        )
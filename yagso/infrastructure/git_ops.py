"""Infrastructure layer for Git operations using gitpython."""

from pathlib import Path
from typing import Dict, List, Any, Optional
from git import Repo, Submodule

from ..domain.submodule import SubmoduleDefinition


class GitOperations:
    """Interface to Git commands using gitpython."""

    def __init__(self, repo_path: Path):
        """Initialize with repository path."""
        self.repo_path = repo_path
        self._repo: Optional[Repo] = None

    @property
    def repo(self) -> Repo:
        """Get or create GitPython Repo object."""
        if self._repo is None:
            try:
                self._repo = Repo(self.repo_path)
            except git.InvalidGitRepositoryError:
                raise ValueError(f"Not a valid Git repository: {self.repo_path}")
        return self._repo

    def get_submodules(self) -> List[Dict[str, Any]]:
        """List all submodules in the repository."""
        submodules = []
        for submodule in self.repo.submodules:
            submodules.append({
                "name": submodule.name,
                "path": submodule.path,
                "url": submodule.url,
                "branch": getattr(submodule, 'branch', 'main'),
                "commit": submodule.hexsha if submodule.hexsha else None,
            })
        return submodules

    def clone_submodule(self, url: str, path: str, branch: str = "main") -> None:
        """Clone a submodule."""
        try:
            # Use git command to add submodule
            self.repo.git.submodule("add", "-b", branch, url, path)
        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to clone submodule {path}: {e}")

    def update_submodule(self, path: str, options: Dict[str, Any]) -> None:
        """Update a specific submodule."""
        try:
            if options.get("init", False):
                # Initialize and update submodule
                self.repo.git.submodule("update", "--init", "--recursive", path)
            else:
                # Just update existing submodules
                self.repo.git.submodule("update", "--recursive", path)

            if options.get("remote", False):
                # Update to latest on remote branch
                submodule_repo_path = self.repo_path / path
                if submodule_repo_path.exists():
                    submodule_repo = Repo(submodule_repo_path)
                    submodule_repo.remotes.origin.pull()

        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to update submodule {path}: {e}")
        except ValueError:
            raise ValueError(f"Submodule not found: {path}")

    def update_all_submodules(self, options: Dict[str, Any]) -> None:
        """Update all submodules."""
        for submodule in self.repo.submodules:
            self.update_submodule(submodule.path, options)

    def commit_all(self, message: str) -> None:
        """Commit all changes recursively."""
        try:
            # Add all changes in main repo
            self.repo.git.add(all=True)

            # Commit if there are changes
            if self.repo.is_dirty() or self.repo.untracked_files:
                self.repo.index.commit(message)
            else:
                raise ValueError("No changes to commit")

            # Also commit in submodules if they have changes
            for submodule in self.repo.submodules:
                if submodule.module_exists():
                    submodule_repo = submodule.module()
                    if submodule_repo.is_dirty() or submodule_repo.untracked_files:
                        submodule_repo.git.add(all=True)
                        submodule_repo.index.commit(f"Update {submodule.name}: {message}")

        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to commit changes: {e}")

    def push_all(self) -> None:
        """Push all commits to remote."""
        try:
            # Push main repository
            origin = self.repo.remote('origin')
            origin.push()

            # Push all submodules
            for submodule in self.repo.submodules:
                if submodule.module_exists():
                    submodule_repo = submodule.module()
                    try:
                        submodule_origin = submodule_repo.remote('origin')
                        submodule_origin.push()
                    except (git.GitCommandError, ValueError):
                        # Skip if submodule has no remote or push fails
                        pass

        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to push changes: {e}")
        except ValueError as e:
            raise RuntimeError(f"No remote origin configured: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get repository status."""
        return {
            "is_dirty": self.repo.is_dirty(),
            "untracked_files": self.repo.untracked_files,
            "modified_files": [item.a_path for item in self.repo.index.diff(None)],
            "staged_files": [item.a_path for item in self.repo.index.diff("HEAD")],
        }

    def is_git_repository(self) -> bool:
        """Check if the path is a valid Git repository."""
        try:
            Repo(self.repo_path)
            return True
        except git.InvalidGitRepositoryError:
            return False
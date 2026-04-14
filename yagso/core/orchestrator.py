"""Core business logic orchestrator for YAGSO."""
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

from ..domain.manifest import Manifest
from ..domain.submodule import SubmoduleDefinition
from ..infrastructure.git_ops import GitOperations
from ..infrastructure.manifest_manager import ManifestManager


class DiffStatus(Enum):
    """Represents the status of differences between manifest and repository."""
    UNCHANGED = 0
    MODIFIED = 1
    ADDED = 2
    REMOVED = 3


class SubmoduleOrchestrator:
    """High-level coordination of submodule operations."""

    def __init__(self, repo_path: Path):
        """Initialize with repository path."""
        self.repo_path = repo_path
        # self.git_ops = GitOperations(repo_path)
        self.manifest_manager = ManifestManager()

    def generate_manifest(self, root_path: Optional[Path] = None) -> Manifest:
        """Generate yagso.yaml from repository structure."""
        if root_path is None:
            root_path = self.repo_path

        manifest = self.manifest_manager.generate_from_repository(root_path)
        manifest_path = root_path / "yagso.yaml"
        self.manifest_manager.save_manifest(manifest, manifest_path)

        return manifest

    def update_submodules(self, options: Dict[str, Any]) -> None:
        """Update/initialize submodules based on manifest."""
        manifest_path = self.repo_path / "yagso.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError("yagso.yaml manifest not found. Run 'yagso generate' first.")

        manifest = self.manifest_manager.load_manifest(manifest_path)

        for submodule_def in manifest.submodules:
            try:
                if options.get("init", False):
                    # Clone if not exists, then update
                    if not (self.repo_path / submodule_def.path).exists():
                        # self.git_ops.clone_submodule(
                        #    submodule_def.url,
                        #    submodule_def.path,
                        #    submodule_def.tracking_branch
                        # )
                        pass
                    else:
                        # self.git_ops.update_submodule(submodule_def.path, options)
                        pass
                else:
                    # Just update existing
                    # self.git_ops.update_submodule(submodule_def.path, options)
                    pass

            except Exception as e:
                raise RuntimeError(f"Failed to process submodule {submodule_def.name}: {e}")

    def configure_repository(self, root_path: Optional[Path] = None) -> None:
        """Apply manifest configuration to repository."""
        if root_path is None:
            root_path = self.repo_path

        manifest_path = root_path / "yagso.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError("yagso.yaml manifest not found. Run 'yagso generate' first.")

        manifest = self.manifest_manager.load_manifest(manifest_path)

        # Validate the manifest before applying configuration
        manifest.validate()

        # Sync submodules with manifest configuration (e.g., .gitmodules, .git/config)
        self._sync_submodules(root_path, manifest)

    def _sync_submodules(self, root_path, manifest: Manifest) -> None:
        """Sync submodules with manifest. """

        submodules = manifest.submodules

        self._sync_child_submodules(root_path, submodules)

    def _sync_child_submodules(
            self,
            root_path: Path,
            submodules: List[SubmoduleDefinition]) -> None:
        childs = []

        git_ops = GitOperations(root_path)
        blocks = git_ops.read_gitmodules_blocks()

        for submodule in submodules:
            #  Find suitable operation sync, add , based on manifest vs current state
            status = self._search_submodule(submodule, blocks)

            if status == DiffStatus.MODIFIED:
                git_ops.sync_submodule(submodule)
            elif status == DiffStatus.ADDED:
                git_ops.add_submodule(submodule)

            if submodule.submodules:
                childs.append(submodule)

        # Remaining blocks that were not matched are removed submodules
        for block in blocks:
            git_ops.remove_submodule(block)

        for submodule in childs:
            new_root = root_path / Path(submodule.root_path)
            self._sync_child_submodules(new_root, submodule.submodules)

    def _search_submodule(self, submodule: SubmoduleDefinition, blocks: list) -> DiffStatus:
        """Search for a submodule by path/url in the manifest."""
        for block in blocks:
            if ((block.get("path") == submodule.path) and (block.get("url") == submodule.url)):
                # Compare commit hashes to determine if modified
                if (block.get("commit") == submodule.commit) \
                        and (block.get("branch") == submodule.tracking_branch) \
                        and (block.get("name") == submodule.name):
                    blocks.remove(block)
                    return DiffStatus.UNCHANGED
                else:
                    blocks.remove(block)
                    return DiffStatus.MODIFIED

        # If not found, it's an added submodule
        return DiffStatus.ADDED

    def commit_changes(self, message: str) -> None:
        """Commit all changes recursively."""
        if not message:
            raise ValueError("Commit message is required")

        # self.git_ops.commit_all(message)

    def push_changes(self) -> None:
        """Push all commits to remote."""
        # self.git_ops.push_all()

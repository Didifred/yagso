"""Core business logic orchestrator for YAGSO."""
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import re
from urllib.parse import urlparse

from ..domain.manifest import Manifest
from ..domain.submodule import SubmoduleDefinition
from ..infrastructure.git_ops import GitOperations
from ..infrastructure.manifest_manager import ManifestManager


class DiffStatus(Enum):
    """Represents the status of differences between manifest and repository."""
    UNCHANGED = 0
    MODIFIED = 1
    ADDED = 2
    MOVED = 3
    REMOVED = 4


@dataclass
class SearchResult:
    status: DiffStatus
    name: str


class SubmoduleOrchestrator:
    """High-level coordination of submodule operations."""

    def __init__(self, repo_path: Path):
        """Initialize with repository path."""
        self.repo_path = repo_path
        self.manifest_manager = ManifestManager()

    def generate_manifest(
            self,
            root_path: Optional[Path] = None,
            create_bom: bool = False) -> Manifest:
        """Generates a YAGSO manifest (yagso.yaml) from the repository's submodule structure.

        This method scans the repository's submodule structure starting from the specified root path
        and generates a manifest file (yagso.yaml) that describes the submodules. The manifest is saved
        in the root directory of the repository.

        Args:
            root_path (Optional[Path]): The root directory of the repository to scan for submodules.
                If not provided, defaults to the repository path set during initialization.

        Returns:
            Manifest: The generated manifest object representing the repository's submodule structure.

        Raises:
            FileNotFoundError: If the specified root_path does not exist or is not a valid directory.
            RuntimeError: If there is an issue generating or saving the manifest.
        """
        if root_path is None:
            root_path = self.repo_path

        manifest = self.manifest_manager.generate_from_repository(root_path)
        manifest_path = root_path / "yagso.yaml"
        self.manifest_manager.save_manifest(manifest, manifest_path)

        # Optionally generate a Bill Of Materials file (BOM.yaml)
        if create_bom:
            bom_path = root_path / "BOM.yaml"
            self.manifest_manager.save_bom(manifest, bom_path, root_path)

        return manifest

    def update_submodules(self, options: Dict[str, Any], root_path: Optional[Path] = None) -> None:
        """Update/initialize submodules recursively."""

        if root_path is None:
            root_path = self.repo_path

        with GitOperations(root_path) as git_ops:
            git_ops.update_all_submodules(options)

    def configure_repository(self, root_path: Optional[Path] = None) -> None:
        """Applies the manifest configuration to synchronize the repository's submodules.

        This method loads the manifest file (yagso.yaml) from the specified root path,
        validates it, and synchronizes the repository's submodules with the manifest.
        It ensures that the .gitmodules file and Git configuration are updated to match
        the manifest's submodule definitions.

        Args:
            root_path (Optional[Path]): The root directory of the repository. If not provided,
                defaults to the repository path set during initialization.

        Raises:
            FileNotFoundError: If the yagso.yaml manifest file does not exist in the specified
                root path. Users should run 'yagso generate' to create the manifest first.
        """
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

    def commit_changes(self, message: str, root_path: Optional[Path] = None) -> None:
        """Commit all changes recursively."""

        if root_path is None:
            root_path = self.repo_path

        if not message:
            raise ValueError("Commit message is required")

        with GitOperations(root_path) as git_ops:
            git_ops.commit_all(message)

    def _sync_submodules(self, root_path, manifest: Manifest) -> None:
        """Sync submodules with manifest. """

        submodules = manifest.submodules

        self._sync_child_submodules(root_path, submodules)

    def _sync_child_submodules(
            self,
            root_path: Path,
            submodules: List[SubmoduleDefinition]) -> None:
        childs = []

        with GitOperations(root_path) as git_ops:
            blocks = git_ops.read_gitmodules_blocks()

            for submodule in submodules:
                #  Find suitable operation sync, add , based on manifest vs current state
                search_result = self._search_submodule(submodule, blocks)

                if search_result.status == DiffStatus.MODIFIED:
                    git_ops.sync_submodule(submodule, search_result.name)
                elif search_result.status == DiffStatus.MOVED:
                    git_ops.move_submodule(search_result.name, submodule.path)
                elif search_result.status == DiffStatus.ADDED:
                    git_ops.add_submodule(submodule)

                if submodule.submodules:
                    childs.append(submodule)

            # Remaining blocks that were not matched are removed submodules
            for block in blocks:
                git_ops.remove_submodule(block)

            for submodule in childs:
                new_root = root_path / Path(submodule.root_path)
                self._sync_child_submodules(new_root, submodule.submodules)

    def _search_submodule(self, submodule: SubmoduleDefinition, blocks: list) -> SearchResult:
        """Search for a submodule by path/url in the manifest submodule blocks and determine its
        status compared to the current repository state.

        Args:
            submodule (SubmoduleDefinition): Submodule definition from the manifest to search for.
            blocks (list): current submodule definitions from .gitmodules

        Returns:
            SearchResult: indicating if the submodule is unchanged, modified, added; and its name
        """

        git_name = ""

        for block in blocks:
            if block.get("path") == submodule.path:
                git_name = block.get("name")
                if (block.get("url") == submodule.url):
                    if (block.get("commit") == submodule.commit) \
                            and (git_name == submodule.name) \
                            and (block.get("branch") == submodule.tracking_branch):
                        blocks.remove(block)
                        return SearchResult(DiffStatus.UNCHANGED, git_name)
                    else:
                        blocks.remove(block)
                        return SearchResult(DiffStatus.MODIFIED, git_name)
                else:
                    # URL change but same repo (eg ssh <-> https)
                    if GitOperations.is_same_repo(block.get("url", ""), submodule.url):
                        blocks.remove(block)
                        return SearchResult(DiffStatus.MODIFIED, git_name)
            else:
                # Check if same url but different path (moved)
                if (block.get("url") == submodule.url) \
                        and (block.get("commit") == submodule.commit) \
                        and (git_name == submodule.name):
                    blocks.remove(block)
                    return SearchResult(DiffStatus.MOVED, git_name)

        # Otherwise, it's considerated as an added submodule
        return SearchResult(DiffStatus.ADDED, submodule.name)

    def push_changes(self) -> None:
        """Push all commits to remote."""
        # self.git_ops.push_all()

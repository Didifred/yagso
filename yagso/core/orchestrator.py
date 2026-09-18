"""Core business logic orchestrator for YAGSO."""
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass

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


@dataclass
class StatusEntry:
    """One submodule's dry-run status vs the repository state."""
    status: DiffStatus
    path: str
    name: Optional[str] = None
    url: Optional[str] = None


class SubmoduleOrchestrator:
    """High-level coordination of submodule operations."""

    def __init__(self, repo_path: Path):
        """Initialize with repository path."""
        self.repo_path = repo_path
        self.manifest_manager = ManifestManager()

    def generate_manifest(
            self,
            root_path: Optional[Path] = None,
            create_bom: bool = False,
            files_pattern: Optional[str] = None) -> Manifest:
        """Generates a YAGSO manifest (yagso.yaml) from the repository's submodule structure.

        This method scans the repository's submodule structure starting from the specified root path
        and generates a manifest file (yagso.yaml) that describes the submodules. The manifest is saved
        in the root directory of the repository.

        Args:
            root_path (Optional[Path]): The root directory of the repository to scan for submodules.
                If not provided, defaults to the repository path set during initialization.
            create_bom (bool): Whether to also generate BOM.yaml.
            files_pattern (Optional[str]): Regular expression used to filter BOM file paths.

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
            self.manifest_manager.save_bom(
                manifest, bom_path, root_path, files_pattern=files_pattern)

        return manifest

    def update_submodules(self, options: Dict[str, Any], root_path: Optional[Path] = None) -> None:
        """Update/initialize submodules recursively."""

        if root_path is None:
            root_path = self.repo_path

        with GitOperations(root_path) as git_ops:
            git_ops.update_all_submodules(options)

    def configure_repository(
            self, root_path: Optional[Path] = None) -> None:
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
        self.manifest_manager.progress_total = self._count_submodules(manifest.submodules)
        self.manifest_manager.progress_current = 0
        self._sync_submodules(root_path, manifest)

    def commit_changes(self, message: str, root_path: Optional[Path] = None) -> None:
        """Commit all changes recursively."""

        if root_path is None:
            root_path = self.repo_path

        with GitOperations(root_path) as git_ops:
            git_ops.commit_all(message)

    def _sync_submodules(
            self,
            root_path,
            manifest: Manifest) -> None:
        """Sync submodules with manifest. """

        submodules = manifest.submodules

        self._sync_child_submodules(root_path, submodules)

    def _sync_child_submodules(
            self,
            root_path: Path,
            submodules: List[SubmoduleDefinition]) -> None:
        """Recursively sync child submodules with manifest."""

        childs = []

        with GitOperations(root_path) as git_ops:
            blocks = git_ops.read_gitmodules_blocks()

            for submodule in submodules:
                #  Find suitable operation sync, add , based on manifest vs current state
                search_result = self._search_submodule(submodule, blocks)

                self.manifest_manager.progress_current += 1

                progress_message = f"Configuring {submodule.root_path}"
                # Imported lazily to keep the core layer free of a hard
                # dependency on the presentation layer (breaks an import cycle).
                from ..cli.formatter import OutputFormatter
                OutputFormatter.instance().progress(
                    self.manifest_manager.progress_current,
                    self.manifest_manager.progress_total,
                    progress_message)

                if search_result.status == DiffStatus.MODIFIED:
                    git_ops.sync_submodule(submodule, search_result.name)
                elif search_result.status == DiffStatus.MOVED:
                    git_ops.move_submodule(search_result.name, submodule.path)
                elif search_result.status == DiffStatus.ADDED:
                    git_ops.add_submodule(submodule)

                if submodule.submodules:
                    childs.append(submodule)
            # end for submodule in submodules

            # Remaining blocks that were not matched are removed submodules
            for block in blocks:
                git_ops.remove_submodule(block)

            for submodule in childs:
                new_root = root_path / Path(submodule.path)
                self._sync_child_submodules(
                    new_root, submodule.submodules)

    def _count_submodules(self, submodules: List[SubmoduleDefinition]) -> int:
        """Count all submodules in a manifest, including nested definitions."""
        return sum(1 + self._count_submodules(submodule.submodules) for submodule in submodules)

    def _search_submodule(self, submodule: SubmoduleDefinition, blocks: list) -> SearchResult:
        """Search for a submodule by path/url in the .gitmodules blocks and
        determine its status compared to the current repository state.

        The primary key of a ``.gitmodules`` entry is its ``path``.  A block
        whose path matches the manifest path is handled first:

        * path + url + commit + name + branch all match → UNCHANGED
        * path matches but url/commit/name/branch differ → MODIFIED
        * path matches, url differs but resolves to the same remote
          (https <-> ssh) → MODIFIED
        * path matches but the url refers to a genuinely different
          repository → ADDED (the old block is left in place so the caller's
          removal pass can drop it)

        When no block has the manifest path, a block with the same url,
        commit AND name at a different path is treated as MOVED — the name
        comparison is made against the *current* block, never against state
        left over from a previous iteration.

        The matched block is removed from ``blocks`` so callers can treat
        the leftovers as REMOVED submodules.

        Args:
            submodule (SubmoduleDefinition): Submodule definition from the
                manifest to search for.
            blocks (list): current submodule definitions from .gitmodules

        Returns:
            SearchResult: indicating if the submodule is unchanged, modified,
                moved or added; and the name of the matching .gitmodules entry
                when one exists.
        """

        # Pass 1: look for the block whose path matches the manifest path.
        for block in blocks:
            if block.get("path") != submodule.path:
                continue

            git_name = block.get("name")

            if block.get("url") == submodule.url:
                # Same URL: unchanged only when commit, name and branch match.
                if (block.get("commit") == submodule.commit) \
                        and (git_name == submodule.name) \
                        and (block.get("branch") == submodule.tracking_branch):
                    blocks.remove(block)
                    return SearchResult(DiffStatus.UNCHANGED, git_name)
                blocks.remove(block)
                return SearchResult(DiffStatus.MODIFIED, git_name)

            # URL changed but same repository (eg ssh <-> https)
            if GitOperations.is_same_repo(block.get("url", ""), submodule.url or ""):
                blocks.remove(block)
                return SearchResult(DiffStatus.MODIFIED, git_name)

            # URL refers to a different repository: leave the old block in
            # place so the caller's removal pass drops it, then re-add.
            return SearchResult(DiffStatus.ADDED, submodule.name or "")

        # Pass 2: no path match — a block with the same url, commit and name
        # at a different path is a moved submodule.
        for block in blocks:
            if (block.get("url") == submodule.url) \
                    and (block.get("commit") == submodule.commit) \
                    and (block.get("name") == submodule.name):
                blocks.remove(block)
                return SearchResult(DiffStatus.MOVED, block.get("name") or "")

        return SearchResult(DiffStatus.ADDED, submodule.name or "")

    def push_changes(self) -> None:
        """Push all commits to remote."""
        with GitOperations(self.repo_path) as git_ops:
            git_ops.push_all()

    def status_report(self, root_path: Optional[Path] = None) -> List[StatusEntry]:
        """Dry-run diff between the manifest (yagso.yaml) and the repository.

        For every submodule declared in the manifest the repository state is
        classified (UNCHANGED / MODIFIED / MOVED / ADDED); .gitmodules blocks
        with no manifest counterpart are reported as REMOVED. Nothing is
        written — this is a read-only preview of what ``configure`` would do.

        Args:
            root_path (Optional[Path]): The root directory of the repository.
                If not provided, defaults to the repository path set during
                initialization.

        Raises:
            FileNotFoundError: If the yagso.yaml manifest file does not exist
                in the specified root path.

        Returns:
            List[StatusEntry]: One entry per manifest submodule plus one per
                orphaned .gitmodules block (REMOVED).
        """
        if root_path is None:
            root_path = self.repo_path

        manifest_path = root_path / "yagso.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError("yagso.yaml manifest not found. Run 'yagso generate' first.")

        manifest = self.manifest_manager.load_manifest(manifest_path)
        manifest.validate()

        with GitOperations(root_path) as git_ops:
            blocks = git_ops.read_gitmodules_blocks()

        return self._diff_manifest(manifest, blocks)

    def _diff_manifest(self, manifest: Manifest, blocks: list) -> List[StatusEntry]:
        """Classify every manifest submodule against the .gitmodules blocks.

        Mutates ``blocks`` the same way ``_sync_child_submodules`` does: each
        matched block is removed, so blocks left over at the end are orphans
        (REMOVED submodules).
        """
        report: List[StatusEntry] = []

        for submodule in manifest.submodules:
            result = self._search_submodule(submodule, blocks)
            report.append(StatusEntry(
                status=result.status,
                path=submodule.root_path,
                name=submodule.name,
                url=submodule.url,
            ))

        # Any block that survived the search has no manifest counterpart.
        for block in blocks:
            report.append(StatusEntry(
                status=DiffStatus.REMOVED,
                path=block.get("path", ""),
                name=block.get("name"),
                url=block.get("url"),
            ))

        return report

"""Infrastructure layer for manifest file operations."""

import yaml
from pathlib import Path
from typing import Optional, List

from .git_ops import GitOperations
from ..domain.manifest import Manifest
from ..domain.submodule import SubmoduleDefinition


class ManifestManager:
    """Handles reading/writing manifest files using Python's native file operations."""

    def __init__(self):
        pass

    def load_manifest(self, path: Path) -> Manifest:
        """Load yagso.yaml manifest from file.

        Args:
            path (Path): file path to load the manifest from

        Raises:
            FileNotFoundError: Manifest file not found at the specified path
            ValueError: Manifest file is empty or contains invalid YAML
            ValueError: Manifest file is missing required fields or has invalid structure

        Returns:
            Manifest: Loaded manifest object
        """
        if not path.exists():
            raise FileNotFoundError(f"Manifest file not found: {path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data is None:
                    raise ValueError("Empty manifest file")
                return Manifest.from_dict(data)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in manifest: {e}")

    def save_manifest(self, manifest: Manifest, path: Path) -> None:
        """Save manifest to yagso.yaml file.

        Args:
            manifest (Manifest): manifest to save
            path (Path): file path to save the manifest to

        Raises:
            IOError: Failed to write manifest to file
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(manifest.to_dict(), f,
                          default_flow_style=False, sort_keys=False)
        except IOError as e:
            raise IOError(f"Failed to save manifest: {e}")

    def generate_from_repository(self, root_path: Path) -> Manifest:
        """Generate manifest from existing .gitmodules file.

        Args:
            root_path (Path): top-level repository path to read .gitmodules from

        Raises:
            FileNotFoundError: No .gitmodules file found at the specified path
            ValueError: No submodules found in .gitmodules or invalid submodule definitions

        Returns:
            Manifest: _description_
        """
        gitmodules_path = root_path / ".gitmodules"

        if not gitmodules_path.exists():
            raise FileNotFoundError(
                f"No .gitmodules file found in {root_path}")

        submodules = self._parse_submodule(root_path, prefix_path=Path(""))

        if not submodules:
            raise ValueError("No submodules found in .gitmodules")

        return Manifest(submodules=submodules)

    def _parse_submodule(self, repo_fs_path: Path, prefix_path: Path = Path("")) -> list:
        """Parse submodule definitions from a .gitmodules file at the given repository filesystem path,
        using GitPython to obtain commit information.

        Args:
            repo_fs_path (Path): Filesystem path to the repository containing the .gitmodules file to parse.
            prefix_path (Path, optional): The submodule relative path. Defaults to Path("").

        Returns:
            list: list of SubmoduleDefinition objects representing the submodules defined in the .gitmodules file.
        """
        gm = repo_fs_path / ".gitmodules"
        if not gm.exists():
            return []

        git_ops = GitOperations(repo_fs_path)
        blocks = git_ops.read_gitmodules_blocks()

        results = []
        for block in blocks:
            sub = self._build_submodule_from_block(block, repo_fs_path, prefix_path, git_ops)
            results.append(sub)

        return results

    def _build_submodule_from_block(
            self,
            block: dict,
            repo_fs_path: Path,
            prefix_path: Path,
            git_ops: GitOperations) -> SubmoduleDefinition:
        """Construct a SubmoduleDefinition from a parsed .gitmodules block using git_ops for git info."""
        name = block.get("name", block.get("path", ""))
        path = block.get("path", name)
        url = block.get("url", "")

        if not name or not path or not url:
            raise ValueError(f"Incomplete submodule definition: {block}")

        branch = block.get("branch")

        # compute full relative path from the top-level root
        if prefix_path and str(prefix_path).strip():
            full_rel = prefix_path / path
        else:
            full_rel = Path(path)
        full_rel_norm = full_rel.as_posix().lstrip('/')

        # normalize url (remove trailing slash)
        url = url.rstrip('/')

        # determine the commit SHA recorded in this repository for the submodule path
        commit = git_ops.get_recorded_commit(path)

        # commit is required — fail fast if we couldn't determine it
        if not commit:
            raise ValueError(
                f"Unable to determine recorded commit for submodule '{name}' at path '{path}' in repository {repo_fs_path}")

        # prepare submodule definition

        # Keep `path` as declared in the submodule definition (relative to
        # that repository) — do not expand to a full relative path from the
        # top-level repo. This preserves the original git submodule `path`.
        sub = SubmoduleDefinition(
            root_path=full_rel_norm,
            name=name,
            path=Path(path).as_posix().lstrip('/'),
            url=url,
            commit=commit,
            tracking_branch=branch,
        )

        # if we have a commit and the submodule worktree exists, try to discover refs
        refs: List[str] = []
        child_fs_path = repo_fs_path / path
        try:
            if commit and child_fs_path.exists():
                refs = git_ops.get_refs_containing_commit_at_path(child_fs_path, commit)
        except Exception:
            refs = []

        if refs:
            sub.ref = refs

        # recurse into the submodule folder if it exists and contains its own .gitmodules
        if child_fs_path.exists() and (child_fs_path / '.gitmodules').exists():
            child_subs = self._parse_submodule(child_fs_path, prefix_path=full_rel)
            if child_subs:
                sub.submodules = child_subs

        return sub

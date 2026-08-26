"""Infrastructure layer for manifest file operations."""

import re
import yaml
from pathlib import Path
from typing import Optional, List

from .git_ops import GitOperations
from ..domain.manifest import Manifest
from ..domain.bom import Bom
from ..domain.submodule import SubmoduleDefinition


class ManifestManager:
    """Handles reading/writing manifest files using Python's native file operations."""

    def __init__(self):
        pass

    def update_submodule_field(self, manifest: Manifest, root_path: str, field_name: str,
                               field_value) -> None:
        """Update a specific field of a submodule identified by root_path.

        Args:
            manifest (Manifest): The manifest to update
            root_path (str): The root_path of the submodule to update
            field_name (str): The field name to update (e.g., 'commit', 'url', 'tracking_branch')
            field_value: The new value for the field

        Raises:
            FileNotFoundError: Submodule not found with the specified root_path
            ValueError: Invalid field name for SubmoduleDefinition

        """
        submodule = self._find_submodule_by_root_path(manifest.submodules, root_path)

        if not submodule:
            raise FileNotFoundError(f"Submodule not found with root_path: {root_path}")

        if not hasattr(submodule, field_name):
            raise ValueError(
                f"Invalid field name '{field_name}' for SubmoduleDefinition")

        setattr(submodule, field_name, field_value)

    def get_submodule_field(self, manifest: Manifest, root_path: str, field_name: str) -> Optional:
        """Get a specific field of a submodule identified by root_path.

        Args:
            manifest (Manifest): The manifest to query
            root_path (str): The root_path of the submodule to query
            field_name (str): The field name to retrieve (e.g., 'commit', 'url', 'tracking_branch')

        Raises:
            ValueError: Submodule not found with the specified root_path
            ValueError: Invalid field name for SubmoduleDefinition

        Returns:
            The value of the specified field for the submodule
        """
        submodule = self._find_submodule_by_root_path(manifest.submodules, root_path)

        if not submodule:
            raise ValueError(f"Submodule not found with root_path: {root_path}")

        if not hasattr(submodule, field_name):
            raise ValueError(
                f"Invalid field name '{field_name}' for SubmoduleDefinition")

        return getattr(submodule, field_name)

    def add_submodule_definition(self, manifest: Manifest, submodule: SubmoduleDefinition) -> None:
        """Add a new submodule to the manifest.

        Args:
            manifest (Manifest): The manifest to update
            submodule (SubmoduleDefinition): The submodule to add

        Raises:
            ValueError: Submodule with the same root_path already exists
        """
        existing_submodule = self._find_submodule_by_root_path(
            manifest.submodules, submodule.root_path)

        if existing_submodule:
            submodule.root_path = existing_submodule.root_path + '/' + submodule.path
            existing_submodule.submodules.append(submodule)
        else:
            manifest.submodules.append(submodule)

    def _find_submodule_by_root_path(self, submodules: List[SubmoduleDefinition],
                                     root_path: str) -> Optional[SubmoduleDefinition]:
        """Recursively find a submodule by its root_path.

        Args:
            submodules (List[SubmoduleDefinition]): List of submodules to search
            root_path (str): The root_path to search for

        Returns:
            Optional[SubmoduleDefinition]: The found submodule or None
        """
        for submodule in submodules:
            if submodule.root_path == root_path:
                return submodule
            if submodule.submodules:
                found = self._find_submodule_by_root_path(submodule.submodules, root_path)
                if found:
                    return found
        return None

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
            raise ValueError(f"Invalid YAML in manifest: {e}") from e

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
            raise IOError(f"Failed to save manifest: {e}") from e

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

        with GitOperations(repo_fs_path) as git_ops:
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
        """Construct a SubmoduleDefinition from a parsed .gitmodules block using git_ops for git info.

        This method builds a complete SubmoduleDefinition by combining information from
        the .gitmodules block with git repository state information. It also recursively
        discovers nested submodules if they exist.

        Args:
            block (dict): A parsed .gitmodules block containing submodule configuration
                         (name, path, url, and optional branch).
            repo_fs_path (Path): Filesystem path to the repository containing the .gitmodules file.
            prefix_path (Path): The relative path prefix for nested submodules to compute
                               the full root_path.
            git_ops (GitOperations): GitOperations instance to retrieve commit SHA and refs
                                     for the submodule.

        Raises:
            ValueError: If the block is missing required fields (name, path, or url).
            ValueError: If unable to determine the recorded commit SHA for the submodule.

        Returns:
            SubmoduleDefinition: A fully constructed SubmoduleDefinition object with commit,
                                refs, and any nested submodules discovered.
        """
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
                f"Unable to determine recorded commit for submodule '{name}' at path '{path}' in "
                f"repository {repo_fs_path}")

        # Prepare submodule definition

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

        child_fs_path = repo_fs_path / path
        with GitOperations(child_fs_path) as git_ops:
            # Check if a branch in checkouted
            # If head is not detached, record the active branch name as active_branch
            if not git_ops.repo.head.is_detached:
                sub.active_branch = git_ops.repo.active_branch.name

            # If we have a commit and the submodule worktree exists, try to discover refs
            refs: List[str] = []
            try:
                refs = git_ops.get_refs_containing_commit_at_path(commit)
            except Exception:
                refs = []

            if refs:
                sub.ref = refs

        # Recurse into the submodule folder that shall contains its own .gitmodules
        if child_fs_path.exists() and (child_fs_path / '.gitmodules').exists():
            child_subs = self._parse_submodule(child_fs_path, prefix_path=full_rel)
            if child_subs:
                sub.submodules = child_subs

        return sub

    def _choose_preferred_ref(self, refs: Optional[List[str]]) -> Optional[str]:
        """Return the first ref entry (trim surrounding quotes)."""
        if not refs:
            return None

        first = refs[0]
        if not first:
            return None

        # strip surrounding single/double quotes if present
        return first.strip().strip("'\"")

    def _list_files(
            self,
            repo_root: Path,
            sub_root: str,
            child_submodules: List[SubmoduleDefinition],
            files_pattern: Optional[str] = None) -> List[str]:
        """List files under a submodule filesystem path, excluding nested submodule folders and .git."""
        fs_path = repo_root / sub_root
        if not fs_path.exists() or not fs_path.is_dir():
            return []

        child_names = {c.path for c in child_submodules} if child_submodules else set()
        files: List[str] = []

        for p in fs_path.rglob('*'):
            if not p.is_file():
                continue
            # skip anything under a .git folder
            if '.git' in p.parts:
                continue

            # skip files that are under a nested submodule top-level folder
            rel = p.relative_to(fs_path)
            if rel.parts and rel.parts[0] in child_names:
                continue

            # skip common git metadata files
            if rel.name in {'.gitmodules', '.gitignore', '.gitattributes'}:
                continue

            relative_path = rel.as_posix()
            if files_pattern is None or re.search(files_pattern, relative_path):
                files.append(relative_path)

        return sorted(files)

    def save_bom(
            self,
            manifest: Manifest,
            path: Path,
            repo_root: Path,
            files_pattern: Optional[str] = None) -> None:
        """Save a Bill Of Materials (BOM.yaml) reflecting repository paths and a single preferred ref per submodule.

        The BOM mirrors the structure of yagso.yaml (version + submodules), but each submodule entry only keeps
        the `path` (not the name), a single `ref` chosen by priority (tag, remote branch, local branch), and a
        `files` list containing files in the repository at that submodule path.
        """
        def _conv(sub: SubmoduleDefinition):
            entry = {"path": sub.path}

            # keep commit as requested
            if getattr(sub, 'commit', None):
                entry["commit"] = sub.commit

            chosen = self._choose_preferred_ref(getattr(sub, 'ref', None))
            if chosen:
                entry["ref"] = chosen

            # list files for this submodule (exclude nested submodules)
            files = self._list_files(
                repo_root, sub.root_path, sub.submodules, files_pattern=files_pattern)
            if files:
                entry["files"] = files

            if sub.submodules:
                entry["submodules"] = [_conv(c) for c in sub.submodules]

            return entry

        bom = {
            "version": getattr(manifest, 'version', '1.0'),
            "submodules": [_conv(s) for s in manifest.submodules]
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(bom, f, default_flow_style=False, sort_keys=False)
        except IOError as e:
            raise IOError(f"Failed to save BOM: {e}") from e

    def load_bom(self, path: Path) -> Bom:
        """Load BOM.yaml manifest from file.

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
                return Bom.from_dict(data)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in manifest: {e}") from e

    def get_submodule_field(self, bom: Bom, root_path: str, field_name: str) -> Optional:
        """Get a specific field of a submodule identified by root_path.

        Args:
            bom (Bom): The manifest to query
            root_path (str): The root_path of the submodule to query
            field_name (str): The field name to retrieve (e.g., 'commit', 'url', 'tracking_branch')

        Raises:
            FileNotFoundError: Submodule not found with the specified root_path
            ValueError: Invalid field name for SubmoduleDefinition

        Returns:
            The value of the specified field for the submodule
        """
        submodule = self._find_submodule_by_root_path(bom.submodules, root_path)

        if not submodule:
            raise FileNotFoundError(f"Submodule not found with root_path: {root_path}")

        if not hasattr(submodule, field_name):
            raise ValueError(
                f"Invalid field name '{field_name}' for SubmoduleDefinition")

        return getattr(submodule, field_name)

"""Infrastructure layer for manifest file operations."""

import yaml
import subprocess
import re
from pathlib import Path
from typing import Optional, List

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

        submodules = self._parse_file(root_path, prefix_path=Path(""))

        if not submodules:
            raise ValueError("No submodules found in .gitmodules")

        return Manifest(submodules=submodules)

    def _parse_file(self, repo_fs_path: Path, prefix_path: Path = Path("")) -> list:
        """Parse a .gitmodules file and return a list of SubmoduleDefinition objects.

        Args:
            repo_fs_path (Path): path to the repository folder containing .gitmodules
            prefix_path (Path, optional): prefix to apply to nested paths when computing full relative path

        Returns:
            list: list of SubmoduleDefinition instances (children attached)
        """
        gm = repo_fs_path / ".gitmodules"
        if not gm.exists():
            return []

        blocks = []
        current = {}
        try:
            with open(gm, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('[submodule'):
                        if current:
                            blocks.append(current)
                        # extract name between quotes
                        try:
                            nm = line.split('"')[1]
                        except Exception:
                            nm = ''
                        current = {"name": nm}
                    elif line and '=' in line:
                        key, value = line.split('=', 1)
                        current[key.strip()] = value.strip()

                if current:
                    blocks.append(current)
        except IOError as e:
            raise IOError(f"Failed to read .gitmodules at {gm}: {e}")

        results = []
        for block in blocks:
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
            commit = None
            try:
                proc = subprocess.run([
                    "git", "ls-tree", "HEAD", "--", path
                ], cwd=str(repo_fs_path), capture_output=True, text=True)
                out = proc.stdout.strip()
                if out:
                    m = re.search(r"commit\s+([0-9a-fA-F]{7,40})", out)
                    if m:
                        commit = m.group(1)
            except Exception:
                commit = None

            # commit is required — fail fast if we couldn't determine it
            if not commit:
                raise ValueError(
                    f"Unable to determine recorded commit for submodule '{name}' at path '{path}' in repository {repo_fs_path}")

            # prepare submodule definition
            sub = SubmoduleDefinition(
                name=name,
                path=full_rel_norm,
                url=url,
                commit=commit,
                tracking_branch=branch,
            )

            # if we have a commit and the submodule worktree exists, try to discover refs
            refs: List[str] = []
            child_fs_path = repo_fs_path / path
            try:
                if commit and child_fs_path.exists():
                    # ensure this is a git repo (handles .git file pointing to gitdir)
                    rproc = subprocess.run(["git",
                                            "-C",
                                            str(child_fs_path),
                                            "rev-parse",
                                            "--git-dir"],
                                           capture_output=True,
                                           text=True)
                    if rproc.returncode == 0:
                        # list branches/tags/remotes that contain this commit
                        refproc = subprocess.run([
                            "git", "-C", str(child_fs_path),
                            "for-each-ref", "--format=%(refname:short)", "--contains", commit,
                            "refs/heads", "refs/tags", "refs/remotes"
                        ], capture_output=True, text=True)
                        if refproc.returncode == 0 and refproc.stdout.strip():
                            refs = [r.strip() for r in refproc.stdout.splitlines() if r.strip()]
            except Exception:
                refs = []

            if refs:
                sub.ref = refs

            # recurse into the submodule folder if it exists and contains its own .gitmodules
            if child_fs_path.exists() and (child_fs_path / '.gitmodules').exists():
                child_subs = self._parse_file(child_fs_path, prefix_path=full_rel)
                if child_subs:
                    sub.submodules = child_subs

            results.append(sub)

        return results

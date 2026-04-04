"""Infrastructure layer for manifest file operations."""

import yaml
from pathlib import Path
from typing import Optional

from ..domain.manifest import Manifest
from ..domain.submodule import SubmoduleDefinition


class ManifestManager:
    """Handles reading/writing manifest files using Python's native file operations."""

    def __init__(self):
        pass

    def load_manifest(self, path: Path) -> Manifest:
        """Load yagso.yaml manifest from file."""
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
        """Save manifest to yagso.yaml file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(manifest.to_dict(), f, default_flow_style=False, sort_keys=False)
        except IOError as e:
            raise IOError(f"Failed to save manifest: {e}")

    def generate_from_repository(self, root_path: Path) -> Manifest:
        """Generate manifest from existing .gitmodules file."""
        gitmodules_path = root_path / ".gitmodules"

        if not gitmodules_path.exists():
            raise FileNotFoundError(f"No .gitmodules file found in {root_path}")

        submodules = []
        current_submodule = {}

        try:
            with open(gitmodules_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('[submodule'):
                        # Save previous submodule if exists
                        if current_submodule:
                            submodules.append(self._parse_submodule_block(current_submodule))
                        current_submodule = {"name": line.split('"')[1]}
                    elif line and '=' in line:
                        key, value = line.split('=', 1)
                        current_submodule[key.strip()] = value.strip()

                # Don't forget the last submodule
                if current_submodule:
                    submodules.append(self._parse_submodule_block(current_submodule))

        except IOError as e:
            raise IOError(f"Failed to read .gitmodules: {e}")

        if not submodules:
            raise ValueError("No submodules found in .gitmodules")

        return Manifest(submodules=submodules)

    def _parse_submodule_block(self, block: dict) -> 'SubmoduleDefinition':
        """Parse a submodule block from .gitmodules into SubmoduleDefinition."""

        name = block.get("name", block.get("path", ""))
        path = block.get("path", name)
        url = block.get("url", "")

        if not name or not path or not url:
            raise ValueError(f"Incomplete submodule definition: {block}")

        branch = block.get("branch", None)

        # Submodule URLs should not end with a slash, as it can cause issues with git commands
        if url.endswith("/"):
            url = url[:-1]

        return SubmoduleDefinition(
            name=name,
            path=path,
            url=url,
            tracking_branch=branch
        )
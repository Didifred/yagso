"""Core business logic orchestrator for YAGSO."""

from pathlib import Path
from typing import Dict, Any, Optional

from ..domain.manifest import Manifest
from ..infrastructure.git_ops import GitOperations
from ..infrastructure.manifest_manager import ManifestManager


class SubmoduleOrchestrator:
    """High-level coordination of submodule operations."""

    def __init__(self, repo_path: Path):
        """Initialize with repository path."""
        self.repo_path = repo_path
        self.git_ops = GitOperations(repo_path)
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
                        self.git_ops.clone_submodule(
                            submodule_def.url,
                            submodule_def.path,
                            submodule_def.tracking_branch
                        )
                    else:
                        self.git_ops.update_submodule(submodule_def.path, options)
                else:
                    # Just update existing
                    self.git_ops.update_submodule(submodule_def.path, options)

            except Exception as e:
                raise RuntimeError(f"Failed to process submodule {submodule_def.name}: {e}")

    def configure_repository(self) -> None:
        """Apply manifest configuration to repository."""
        manifest_path = self.repo_path / "yagso.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError("yagso.yaml manifest not found. Run 'yagso generate' first.")

        manifest = self.manifest_manager.load_manifest(manifest_path)

        # For now, this is mainly a validation step
        # Future enhancements could apply additional configuration
        manifest.validate()

        # Ensure .gitmodules matches manifest
        self._sync_gitmodules(manifest)

    def _sync_gitmodules(self, manifest: Manifest) -> None:
        """Sync .gitmodules file with manifest."""
        gitmodules_path = self.repo_path / ".gitmodules"

        # Generate .gitmodules content from manifest
        content = ""
        for submodule in manifest.submodules:
            content += f'[submodule "{submodule.name}"]\n'
            content += f'\tpath = {submodule.path}\n'
            content += f'\turl = {submodule.url}\n'
            content += '\n'

        # Write .gitmodules
        with open(gitmodules_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Add to git if not already tracked
        try:
            self.git_ops.repo.git.add(".gitmodules")
        except Exception:
            pass  # Ignore if already added

    def commit_changes(self, message: str) -> None:
        """Commit all changes recursively."""
        if not message:
            raise ValueError("Commit message is required")

        self.git_ops.commit_all(message)

    def push_changes(self) -> None:
        """Push all commits to remote."""
        self.git_ops.push_all()
"""Command handlers for YAGSO CLI."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from pathlib import Path
from .orchestrator import SubmoduleOrchestrator
from ..cli.formatter import OutputFormatter


class CommandHandler(ABC):
    """Base class for command handlers."""

    def __init__(self, orchestrator: SubmoduleOrchestrator):
        self.orchestrator = orchestrator

    @abstractmethod
    def execute(self, options: Dict[str, Any]) -> None:
        """Execute the command with given options."""
        raise NotImplementedError()


class GenerateHandler(CommandHandler):
    """Handler for 'generate' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        formatter = OutputFormatter()

        root_path = options.get("root_path")
        root_path = Path(root_path) if root_path else Path.cwd()

        if not (root_path / ".git").exists():
            raise ValueError(f"Not a Git repository: {root_path}")

        manifest = self.orchestrator.generate_manifest(root_path)
        formatter.success(f"Generated manifest with {len(manifest.submodules)} submodules")


class UpdateHandler(CommandHandler):
    """Handler for 'update' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        formatter = OutputFormatter()

        self.orchestrator.update_submodules(options)
        init_msg = " and initialized" if options.get("init", False) else ""
        remote_msg = " from remote" if options.get("remote", False) else ""
        formatter.success(f"Updated submodules{init_msg}{remote_msg}")


class ConfigureHandler(CommandHandler):
    """Handler for 'configure' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        formatter = OutputFormatter()

        root_path = options.get("root_path")
        root_path = Path(root_path) if root_path else Path.cwd()

        if not (root_path / ".git").exists():
            raise ValueError(f"Not a Git repository: {root_path}")

        self.orchestrator.configure_repository(root_path)
        formatter.success("Repository configured according to manifest")


class CommitHandler(CommandHandler):
    """Handler for 'commit' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        formatter = OutputFormatter()

        message = options.get("message", "")
        if not message:
            raise ValueError("Commit message is required")

        self.orchestrator.commit_changes(message)
        formatter.success(f"Committed changes: {message}")


class PushHandler(CommandHandler):
    """Handler for 'push' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        formatter = OutputFormatter()

        self.orchestrator.push_changes()
        formatter.success("Pushed all changes to remote")


__all__ = [
    "CommandHandler",
    "GenerateHandler",
    "UpdateHandler",
    "ConfigureHandler",
    "CommitHandler",
    "PushHandler",
]

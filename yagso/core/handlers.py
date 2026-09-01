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

    def get_formatter(self) -> OutputFormatter:
        """Get the output formatter from the orchestrator."""
        return self.orchestrator.formater


class GenerateHandler(CommandHandler):
    """Handler for 'generate' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()
        create_bom = options.get("BOM", False)
        files_pattern = options.get("files")

        manifest = self.orchestrator.generate_manifest(
            root_path,
            create_bom=create_bom,
            files_pattern=files_pattern,
        )
        self.get_formatter().success(f"Manifest generated completely")


class UpdateHandler(CommandHandler):
    """Handler for 'update' command."""

    def execute(self, options: Dict[str, Any]) -> None:

        root_path = Path.cwd()

        self.orchestrator.update_submodules(options, root_path)

        init_msg = " and initialized" if options.get("init", False) else ""
        remote_msg = " from remote" if options.get("remote", False) else ""
        self.get_formatter().success(f"Updated submodules{init_msg}{remote_msg}")


class ConfigureHandler(CommandHandler):
    """Handler for 'configure' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()

        self.orchestrator.configure_repository(root_path)

        # Regenerate the manifest after configuration to reflect any changes made during the process
        manifest = self.orchestrator.generate_manifest(
            root_path, False)

        self.get_formatter().success(f"Repository configured according to manifest")


class CommitHandler(CommandHandler):
    """Handler for 'commit' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        formatter = OutputFormatter()
        root_path = Path.cwd()

        message = options.get("message", "")
        if not message:
            raise ValueError("Commit message is required")

        self.orchestrator.commit_changes(message, root_path)
        self.get_formatter().success(f"Committed changes: {message}")


class PushHandler(CommandHandler):
    """Handler for 'push' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        formatter = OutputFormatter()

        self.orchestrator.push_changes()
        self.get_formatter().success("Pushed all changes to remote")


__all__ = [
    "CommandHandler",
    "GenerateHandler",
    "UpdateHandler",
    "ConfigureHandler",
    "CommitHandler",
    "PushHandler",
]

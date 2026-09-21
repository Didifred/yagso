"""Command handlers for YAGSO CLI."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from pathlib import Path
from .orchestrator import SubmoduleOrchestrator
from ..output import NullOutput, OutputPort


class CommandHandler(ABC):
    """Base class for command handlers."""

    def __init__(self, orchestrator: SubmoduleOrchestrator,
                 output: OutputPort = None):
        """Initialize the handler with its application services."""
        self.orchestrator = orchestrator
        self.output = output or NullOutput()

    @abstractmethod
    def execute(self, options: Dict[str, Any]) -> None:
        """Execute the command with given options."""
        raise NotImplementedError()


class GenerateHandler(CommandHandler):
    """Handler for 'generate' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()
        create_bom = options.get("BOM", False)
        files_pattern = options.get("files")

        self.orchestrator.generate_manifest(
            root_path,
            create_bom=create_bom,
            files_pattern=files_pattern,
        )
        self.output.success("Manifest generated completely")


class UpdateHandler(CommandHandler):
    """Handler for 'update' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()

        self.orchestrator.update_submodules(options, root_path)

        init_msg = " and initialized" if options.get("init", False) else ""
        remote_msg = " from remote" if options.get("remote", False) else ""
        self.output.success(f"Updated submodules{init_msg}{remote_msg}")


class ConfigureHandler(CommandHandler):
    """Handler for 'configure' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()

        self.orchestrator.configure_repository(root_path)

        # Regenerate the manifest after configuration to reflect any changes made during the process
        self.orchestrator.generate_manifest(root_path, False)

        self.output.success("Repository configured according to manifest")


class CommitHandler(CommandHandler):
    """Handler for 'commit' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()

        message = options.get("message", "")
        if not message:
            raise ValueError("Commit message is required")

        self.orchestrator.commit_changes(message, root_path)
        self.output.success(f"Committed changes: {message}")


class StatusHandler(CommandHandler):
    """Handler for 'status' command (dry-run diff repository vs manifest)."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()

        result = self.orchestrator.status_report(root_path)
        if not result:
            self.output.success("No changes")
        else:
            self.output.success("Status completed")


class PushHandler(CommandHandler):
    """Handler for 'push' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        dry_run = options.get("dry_run", False)
        summaries = self.orchestrator.push_changes(dry_run)
        if dry_run:
            self.output.info("Command will push :")
            for summary in summaries:
                self.output.print(summary)
        self.output.success("Pushed all changes to remote")


__all__ = [
    "CommandHandler",
    "GenerateHandler",
    "UpdateHandler",
    "ConfigureHandler",
    "StatusHandler",
    "CommitHandler",
    "StatusHandler",
    "PushHandler",
]

"""Command handlers for YAGSO CLI."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from pathlib import Path
from .orchestrator import SubmoduleOrchestrator


def _formatter():
    """Return the shared OutputFormatter.

    Imported lazily (inside the function body) so that core modules never
    force-load the presentation layer at import time — importing
    ``yagso.core.handlers`` via ``yagso.core`` used to trip a circular
    import through ``yagso.cli`` → ``yagso.cli.controller``.
    """
    from ..cli.formatter import OutputFormatter
    return OutputFormatter.instance()


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
        root_path = Path.cwd()
        create_bom = options.get("BOM", False)
        files_pattern = options.get("files")

        manifest = self.orchestrator.generate_manifest(
            root_path,
            create_bom=create_bom,
            files_pattern=files_pattern,
        )
        _formatter().success(f"Manifest generated completely")


class UpdateHandler(CommandHandler):
    """Handler for 'update' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()

        self.orchestrator.update_submodules(options, root_path)

        init_msg = " and initialized" if options.get("init", False) else ""
        remote_msg = " from remote" if options.get("remote", False) else ""
        _formatter().success(f"Updated submodules{init_msg}{remote_msg}")


class ConfigureHandler(CommandHandler):
    """Handler for 'configure' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()

        self.orchestrator.configure_repository(root_path)

        # Regenerate the manifest after configuration to reflect any changes made during the process
        manifest = self.orchestrator.generate_manifest(
            root_path, False)

        _formatter().success(f"Repository configured according to manifest")


class CommitHandler(CommandHandler):
    """Handler for 'commit' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()

        message = options.get("message", "")
        if not message:
            raise ValueError("Commit message is required")

        self.orchestrator.commit_changes(message, root_path)
        _formatter().success(f"Committed changes: {message}")


class StatusHandler(CommandHandler):
    """Handler for 'status' command (dry-run diff manifest vs repository)."""

    def execute(self, options: Dict[str, Any]) -> None:
        root_path = Path.cwd()

        report = self.orchestrator.status_report(root_path)

        if not report:
            _formatter().info("No submodules declared in the manifest")
            return

        _formatter().table(
            ["Status", "Path", "Name", "URL"],
            [[r.status.name, r.path, r.name or "-", r.url or "-"] for r in report],
            title="Manifest vs repository")
        _formatter().success("Status computed")


class PushHandler(CommandHandler):
    """Handler for 'push' command."""

    def execute(self, options: Dict[str, Any]) -> None:

        self.orchestrator.push_changes()
        _formatter().success("Pushed all changes to remote")


__all__ = [
    "CommandHandler",
    "GenerateHandler",
    "UpdateHandler",
    "ConfigureHandler",
    "StatusHandler",
    "CommitHandler",
    "PushHandler",
]

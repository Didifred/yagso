"""Command handlers for YAGSO CLI."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from pathlib import Path
from ..orchestrator import SubmoduleOrchestrator
from ...cli.formatter import OutputFormatter


class CommandHandler(ABC):
    """Base class for command handlers."""

    def __init__(self, orchestrator: "SubmoduleOrchestrator"):
        self.orchestrator = orchestrator

    @abstractmethod
    def execute(self, options: Dict[str, Any]) -> None:
        """Execute the command with given options."""
        pass


"""Command handlers for YAGSO CLI."""

class CommandHandler(ABC):
    """Base class for command handlers."""

    def __init__(self, orchestrator: "SubmoduleOrchestrator"):
        self.orchestrator = orchestrator

    @abstractmethod
    def execute(self, options: Dict[str, Any]) -> None:
        """Execute the command with given options."""
        pass


class GenerateHandler(CommandHandler):
    """Handler for 'generate' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        """Generate manifest from repository."""
        formatter = OutputFormatter()

        root_path = options.get("root_path")
        if root_path:
            root_path = Path(root_path)
        else:
            root_path = Path.cwd()

        if not (root_path / ".git").exists():
            raise ValueError(f"Not a Git repository: {root_path}")

        manifest = self.orchestrator.generate_manifest(root_path)
        formatter.success(f"Generated manifest with {len(manifest.submodules)} submodules")


class UpdateHandler(CommandHandler):
    """Handler for 'update' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        """Update submodules."""
        formatter = OutputFormatter()

        self.orchestrator.update_submodules(options)
        init_msg = " and initialized" if options.get("init", False) else ""
        remote_msg = " from remote" if options.get("remote", False) else ""
        formatter.success(f"Updated submodules{init_msg}{remote_msg}")


class ConfigureHandler(CommandHandler):
    """Handler for 'configure' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        """Apply manifest configuration."""
        formatter = OutputFormatter()

        self.orchestrator.configure_repository()
        formatter.success("Repository configured according to manifest")


class CommitHandler(CommandHandler):
    """Handler for 'commit' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        """Commit changes."""
        formatter = OutputFormatter()

        message = options.get("message", "")
        if not message:
            raise ValueError("Commit message is required")

        self.orchestrator.commit_changes(message)
        formatter.success(f"Committed changes: {message}")


class PushHandler(CommandHandler):
    """Handler for 'push' command."""

    def execute(self, options: Dict[str, Any]) -> None:
        """Push changes."""
        formatter = OutputFormatter()

        self.orchestrator.push_changes()
        formatter.success("Pushed all changes to remote")
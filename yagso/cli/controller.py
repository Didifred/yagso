"""Main CLI controller for YAGSO."""

from pathlib import Path
from typing import Dict, Any

from .parser import ArgumentParser
from .formatter import OutputFormatter
from ..core.orchestrator import SubmoduleOrchestrator
from ..core.handlers import (
    GenerateHandler,
    UpdateHandler,
    ConfigureHandler,
    CommitHandler,
    PushHandler,
)


class CLIController:
    """Main entry point, command routing, argument parsing."""

    def __init__(self):
        self.parser = ArgumentParser()
        self.formatter = OutputFormatter()

    def run(self, args: list) -> int:
        """Parse arguments and dispatch to appropriate command."""
        try:
            options = self.parser.parse(args)

            if not options.get("command"):
                return 0  # Help was shown or no command specified

            self.parser.validate(options)

            # Determine repository path
            repo_path = Path.cwd()
            if options.get("command") == "generate" and options.get("root_path"):
                repo_path = Path(options["root_path"])

            # Check if it's a git repository (except for generate which can create manifest)
            if options["command"] != "generate" and not (repo_path / ".git").exists():
                self.formatter.error(f"Not a Git repository: {repo_path}")
                return 1

            # Create orchestrator and handler
            orchestrator = SubmoduleOrchestrator(repo_path)
            handler = self._create_handler(options["command"], orchestrator)

            # Execute command
            handler.execute(options)

            return 0

        except ValueError as e:
            self.formatter.error(str(e))
            return 1
        except FileNotFoundError as e:
            self.formatter.error(str(e))
            return 1
        except RuntimeError as e:
            self.formatter.error(str(e))
            return 1
        except Exception as e:
            self.formatter.error(f"Unexpected error: {e}")
            return 1

    def _create_handler(self, command: str, orchestrator: SubmoduleOrchestrator):
        """Create appropriate handler for command."""
        handlers = {
            "generate": GenerateHandler,
            "update": UpdateHandler,
            "configure": ConfigureHandler,
            "commit": CommitHandler,
            "push": PushHandler,
        }

        handler_class = handlers.get(command)
        if not handler_class:
            raise ValueError(f"Unknown command: {command}")

        return handler_class(orchestrator)
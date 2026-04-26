"""Main CLI controller for YAGSO."""

from pathlib import Path
from typing import Dict, Any

from .parser import ArgumentParser
from .formatter import OutputFormatter
import traceback
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
    SUCCESS = 0
    FAILURE = 1

    def __init__(self, debug: bool = False):
        self.parser = ArgumentParser()
        self.formatter = OutputFormatter()
        self.debug = debug  # Set to True to enable debug output

    def run(self, args: list) -> int:
        """Parse arguments and dispatch to appropriate command."""

        try:
            options = self.parser.parse(args)

            if not options.get("command"):
                return self.SUCCESS  # Help was shown or no command specified

            self.parser.validate(options)

            # Determine repository path
            repo_path = Path.cwd()
            if options.get("root_path"):
                repo_path = Path(options["root_path"])

            # Check if it's a git repository (except for generate which can create manifest)
            if not (repo_path / ".git").exists():
                self.formatter.error(f"Not a Git repository: {repo_path}")
                return self.FAILURE

            # Create orchestrator and handler
            orchestrator = SubmoduleOrchestrator(repo_path)
            handler = self._create_handler(options["command"], orchestrator)

            # Execute command
            handler.execute(options)

            return self.SUCCESS

        except ValueError as e:
            self.formatter.error(str(e))
            if self.debug:
                self.formatter.error(traceback.format_exc())
            return self.FAILURE
        except FileNotFoundError as e:
            self.formatter.error(str(e))
            if self.debug:
                self.formatter.error(traceback.format_exc())
            return self.FAILURE
        except RuntimeError as e:
            self.formatter.error(str(e))
            if self.debug:
                self.formatter.error(traceback.format_exc())
            return self.FAILURE
        except Exception as e:
            self.formatter.error(f"Unexpected error: {e}")
            if self.debug:
                self.formatter.error(traceback.format_exc())
            return self.FAILURE

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

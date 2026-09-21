"""Main CLI controller for YAGSO."""

from pathlib import Path
import traceback

from .parser import ArgumentParser
from .formatter import get_output_formatter
from ..core.orchestrator import SubmoduleOrchestrator
from ..core.handlers import (
    GenerateHandler,
    UpdateHandler,
    ConfigureHandler,
    StatusHandler,
    CommitHandler,
    PushHandler,
)


class CLIController:
    """Main entry point, command routing, argument parsing."""
    SUCCESS = 0
    FAILURE = 1

    def __init__(self, debug: bool = False):
        self.parser = ArgumentParser()
        self.debug = debug  # Set to True to enable debug output
        self.output = get_output_formatter()

    def set_debug(self, debug: bool):
        """Set debug mode

        Arguments:
            debug (bool): activate traceback of exceptions
        """
        self.debug = debug

    def run(self, args: list) -> int:
        """Parse arguments and dispatch to appropriate command."""

        try:
            options = self.parser.parse(args)

            if not options.get("command"):
                return self.SUCCESS  # Help was shown or no command specified

            self.set_debug(options.get("debug", False))
            self.parser.validate(options)

            # Determine repository path
            repo_path = Path.cwd()

            # Check if it's a git repository
            if not (repo_path / ".git").exists():
                self.output.error(f"Not a Git repository: {repo_path}")
                return self.FAILURE

            # Create orchestrator and handler
            orchestrator = SubmoduleOrchestrator(repo_path, self.output)
            handler = self._create_handler(options["command"], orchestrator)

            # Execute command
            handler.execute(options)

            return self.SUCCESS

        except Warning as e:
            # Warning-level conditions are informational and should not fail the CLI.
            self.output.info(str(e))
            return self.SUCCESS

        except Exception as e:
            # Catch all exceptions at the CLI boundary (catch late principle)
            self.output.error(str(e))
            if self.debug:
                self.output.error(traceback.format_exc())
            return self.FAILURE

    def _create_handler(self, command: str, orchestrator: SubmoduleOrchestrator):
        """Create appropriate handler for command."""
        handlers = {
            "generate": GenerateHandler,
            "update": UpdateHandler,
            "configure": ConfigureHandler,
            "status": StatusHandler,
            "commit": CommitHandler,
            "push": PushHandler,
        }

        handler_class = handlers.get(command)
        if not handler_class:
            raise ValueError(f"Unknown command: {command}")

        return handler_class(orchestrator, self.output)

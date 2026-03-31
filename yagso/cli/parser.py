"""CLI argument parsing using argparse."""

import argparse
from typing import Dict, Any


class ArgumentParser:
    """Parse and validate command-line arguments using argparse."""

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            prog="yagso",
            description="Yet Another Git Submodule Orchestrator"
        )
        self._setup_subparsers()

    def _setup_subparsers(self):
        """Set up subcommands."""
        subparsers = self.parser.add_subparsers(dest="command", help="Available commands")

        # generate command
        generate_parser = subparsers.add_parser(
            "generate",
            help="Generate yagso.yaml manifest from repository structure"
        )
        generate_parser.add_argument(
            "--root-path",
            help="Root path of the Git repository (default: current directory)"
        )

        # update command
        update_parser = subparsers.add_parser(
            "update",
            help="Update submodules"
        )
        update_parser.add_argument(
            "--init",
            action="store_true",
            help="Initialize and clone submodules if they don't exist"
        )
        update_parser.add_argument(
            "--remote",
            action="store_true",
            help="Update to latest commit on remote tracking branch"
        )

        # configure command
        configure_parser = subparsers.add_parser(
            "configure",
            help="Apply manifest configuration to repository"
        )

        # commit command
        commit_parser = subparsers.add_parser(
            "commit",
            help="Commit changes recursively"
        )
        commit_parser.add_argument(
            "message",
            help="Commit message"
        )

        # push command
        push_parser = subparsers.add_parser(
            "push",
            help="Push all commits to remote repository"
        )

    def parse(self, args: list) -> Dict[str, Any]:
        """Parse raw arguments into structured options."""
        try:
            parsed = self.parser.parse_args(args)
        except SystemExit as e:
            # argparse calls sys.exit for help or errors
            if e.code == 0:
                # Help was shown
                return {"command": None}
            else:
                # Error occurred
                raise ValueError("Invalid command-line arguments")

        if not parsed.command:
            return {"command": None}

        options = {
            "command": parsed.command,
        }

        # Add command-specific options
        if parsed.command == "generate":
            if hasattr(parsed, "root_path") and parsed.root_path:
                options["root_path"] = parsed.root_path

        elif parsed.command == "update":
            options["init"] = getattr(parsed, "init", False)
            options["remote"] = getattr(parsed, "remote", False)

        elif parsed.command == "commit":
            options["message"] = getattr(parsed, "message", "")

        # configure and push have no additional options

        return options

    def validate(self, options: Dict[str, Any]) -> None:
        """Validate argument combinations."""
        command = options.get("command")

        if not command:
            raise ValueError("No command specified")

        if command not in ["generate", "update", "configure", "commit", "push"]:
            raise ValueError(f"Unknown command: {command}")

        # Command-specific validation
        if command == "commit" and not options.get("message"):
            raise ValueError("Commit message is required for commit command")
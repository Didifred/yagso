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
        self.parser.add_argument(
            "--debug",
            action="store_true",
            default=False,
            help=argparse.SUPPRESS,
        )
        self._setup_subparsers()

    def _add_debug_option(self, command_parser: argparse.ArgumentParser) -> None:
        """Add the development-only debug option to a command parser."""
        command_parser.add_argument(
            "--debug",
            action="store_true",
            default=argparse.SUPPRESS,
            help=argparse.SUPPRESS,
        )

    def _setup_subparsers(self):
        """Set up subcommands."""
        subparsers = self.parser.add_subparsers(dest="command", help="Available commands")

        # generate command
        generate_parser = subparsers.add_parser(
            "generate",
            help="Generate a yagso.yaml manifest from the repository structure"
        )
        self._add_debug_option(generate_parser)
        generate_parser.add_argument(
            "--BOM",
            action="store_true",
            help="Also generate a Bill Of Materials file (BOM.yaml) listing repo paths and files"
        )
        generate_parser.add_argument(
            "--files",
            help="Filter BOM files by regular expression"
        )

        # update command
        update_parser = subparsers.add_parser(
            "update",
            help="Update submodules without initializing new ones"
        )
        self._add_debug_option(update_parser)
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
        _configure_parser = subparsers.add_parser(
            "configure",
            help="Apply manifest configuration to repository"
        )
        self._add_debug_option(_configure_parser)

        # status command
        _status_parser = subparsers.add_parser(
            "status",
            help="Dry-run diff between manifest and repository (read-only)"
        )
        self._add_debug_option(_status_parser)

        # commit command
        commit_parser = subparsers.add_parser(
            "commit",
            help="Commit changes recursively, including submodule metadata"
        )
        self._add_debug_option(commit_parser)
        commit_parser.add_argument(
            "--message",
            help="Commit message"
        )

        # push command
        _push_parser = subparsers.add_parser(
            "push",
            help="Push all submodule commits to the remote repository"
        )
        self._add_debug_option(_push_parser)
        _push_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be pushed without pushing changes"
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
            # else Error occurred
            raise ValueError("Invalid command-line arguments") from e

        if not parsed.command:
            self.parser.print_help()
            return {"command": None}

        options = {
            "command": parsed.command,
            "debug": getattr(parsed, "debug", False),
        }

        # Add command-specific options
        if parsed.command == "update":
            options["init"] = getattr(parsed, "init", False)
            options["remote"] = getattr(parsed, "remote", False)
        elif parsed.command == "generate":
            options["BOM"] = getattr(parsed, "BOM", False)
            options["files"] = getattr(parsed, "files", None)

        elif parsed.command == "commit":
            options["message"] = getattr(parsed, "message", "")
        elif parsed.command == "push":
            options["dry_run"] = getattr(parsed, "dry_run", False)

        #  push have no additional options

        return options

    def validate(self, options: Dict[str, Any]) -> None:
        """Validate argument combinations."""
        command = options.get("command")

        if not command:
            raise ValueError("No command specified")

        if command not in ["generate", "update", "configure", "status", "commit", "push"]:
            raise ValueError(f"Unknown command: {command}")

        # Command-specific validation
        if command == "commit" and not options.get("message"):
            raise ValueError("Commit message is required for commit command")

        if command == "generate" and options.get("files") and not options.get("BOM"):
            raise ValueError("--files requires --BOM")

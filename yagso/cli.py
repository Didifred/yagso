"""Main entry point for YAGSO CLI."""

import sys
from .cli.controller import CLIController


def main():
    """Main entry point."""
    controller = CLIController()
    sys.exit(controller.run(sys.argv[1:]))


if __name__ == "__main__":
    main()
"""CLI output formatting."""


class OutputFormatter:
    """Format and display results to user."""

    PROGRESS_WIDTH = 30
    GREEN = "\033[32m"
    RESET = "\033[0m"

    def success(self, message: str) -> None:
        """Display success message."""
        print(f"✓ {message}")

    def error(self, message: str) -> None:
        """Display error message."""
        print(f"✗ Error: {message}")

    def info(self, message: str) -> None:
        """Display info message."""
        print(f"ℹ {message}")

    def progress(self, current: int, total: int, message: str) -> None:
        """Display a pip-style colored progress bar."""
        percentage = min(100, int((current / total) * 100)) if total > 0 else 0
        completed = int(self.PROGRESS_WIDTH * percentage / 100)
        bar = "=" * max(0, completed - 1) + (">" if completed else "")
        bar = bar.ljust(self.PROGRESS_WIDTH, " ")
        print(
            f"\r{self.GREEN}[{bar}]{self.RESET} {percentage:3d}% {message}",
            end="",
            flush=True,
        )
        if current >= total:
            print()

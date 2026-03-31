"""CLI output formatting."""


class OutputFormatter:
    """Format and display results to user."""

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
        """Display progress message."""
        percentage = int((current / total) * 100) if total > 0 else 0
        print(f"[{current}/{total}] {percentage}% {message}")

    def list_items(self, items: list, title: str = "") -> None:
        """Display a list of items."""
        if title:
            print(f"\n{title}:")
        for item in items:
            print(f"  • {item}")

    def show_summary(self, data: dict) -> None:
        """Display a summary of operations."""
        print("\nSummary:")
        for key, value in data.items():
            if isinstance(value, list):
                print(f"  {key}: {len(value)} items")
                for item in value[:5]:  # Show first 5 items
                    print(f"    • {item}")
                if len(value) > 5:
                    print(f"    ... and {len(value) - 5} more")
            else:
                print(f"  {key}: {value}")
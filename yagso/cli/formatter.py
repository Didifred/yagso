"""CLI output formatting with Rich."""

from typing import Optional

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn


class OutputFormatter:
    """Format and display results to user using Rich."""

    PROGRESS_WIDTH = 30

    def __init__(self, console: Optional[Console] = None):
        """Create a formatter bound to a Rich console."""
        self._console = console or Console()
        self._progress = None
        self._task_id = None

    def success(self, message: str) -> None:
        """Display a success message."""
        self._console.print(f"[green]✓[/green] {message}")

    def error(self, message: str) -> None:
        """Display an error message."""
        self._console.print(f"[red]✗ Error:[/red] {message}")

    def info(self, message: str) -> None:
        """Display an informational message."""
        self._console.print(f"[blue]ℹ[/blue] {message}")

    def progress(self, current: int, total: int, message: str) -> None:
        """Display a Rich-based progress bar."""
        if self._progress is None:
            self._progress = Progress(
                BarColumn(
                    bar_width=self.PROGRESS_WIDTH,
                    style="bar.back",
                    complete_style="green",
                    finished_style="green"),
                TaskProgressColumn(),
                TextColumn("|"),
                TextColumn("[dim]{task.description}[/dim]"),
                console=self._console,
                transient=False,
            )
            self._progress.start()
            self._task_id = self._progress.add_task(message, total=total)

        self._progress.update(self._task_id, completed=current, description=message)

        if current >= total:
            self._progress.stop()
            self._progress = None
            self._task_id = None

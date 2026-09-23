"""CLI output formatting with Rich."""

import sys
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn


class OutputFormatter:
    """Format and display results to user using Rich."""

    PROGRESS_WIDTH = 30
    _instance = None

    @classmethod
    def instance(cls) -> "OutputFormatter":
        """Return the process-wide output formatter instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Create a formatter bound to a Rich console."""
        self._console = Console()
        self._progress = None
        self._task_id = None
        self._bar_column = None

    def _supports_unicode(self) -> bool:
        try:
            encoding = sys.stdout.encoding or ""
            return encoding.lower().replace("-", "") in ("utf8", "utf-8")
        except AttributeError:
            return False

    def print(self, message: str) -> None:
        """Simple print."""
        self._console.print(message)

    def success(self, message: str) -> None:
        """Display a success message."""
        check = "✓" if self._supports_unicode() else "OK"
        self._console.print(f"[green]{check}[/green]  {message}")

    def error(self, message: str) -> None:
        """Display an error message."""
        if self._progress is not None:
            self._bar_column.style = "bar.back"
            self._bar_column.complete_style = "red"
            self._bar_column.finished_style = "red"
            self._progress.stop()
            self._progress = None
            self._task_id = None
            self._bar_column = None
        cross = "✗" if self._supports_unicode() else "X"
        self._console.print(f"[red]{cross} Error:[/red]  {message}")

    def info(self, message: str) -> None:
        """Display an informational message."""
        info = "ℹ" if self._supports_unicode() else "i"
        self._console.print(f"[blue]{info}[/blue]  {message}")

    def progress(self, current: int, total: int, message: str) -> None:
        """Display a Rich-based progress bar."""
        if self._progress is None:
            self._bar_column = BarColumn(
                bar_width=self.PROGRESS_WIDTH,
                style="bar.back",
                complete_style="green",
                finished_style="green")
            self._progress = Progress(
                self._bar_column,
                TextColumn("{task.completed}/{task.total}"),
                TextColumn("|"),
                TextColumn("[dim]{task.description}[/dim]"),
                console=self._console,
                transient=False,
            )
            self._progress.start()
            self._task_id = self._progress.add_task(message, total=total)

        # Ensure current displayed is non-negative
        current_updated = max(current, 0)

        self._progress.update(
            self._task_id,
            completed=current_updated,
            total=total,
            description=message or None,
            refresh=True)

        if current >= total:
            self._progress.stop()
            self._progress = None
            self._task_id = None
            self._bar_column = None


def get_output_formatter() -> OutputFormatter:
    """Return the shared Rich-backed output formatter."""
    return OutputFormatter.instance()


__all__ = ["OutputFormatter", "get_output_formatter"]

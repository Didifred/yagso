"""Output ports shared by application layers and presentation adapters."""

from typing import List, Optional, Protocol


class OutputPort(Protocol):
    """Interface used by YAGSO layers to report command output."""

    def success(self, message: str) -> None:
        """Report a successful operation."""

    def error(self, message: str) -> None:
        """Report an error."""

    def info(self, message: str) -> None:
        """Report informational output."""

    def progress(self, current: int, total: int, message: str) -> None:
        """Report operation progress."""

    def table(self, headers: List[str], rows: List[List[str]],
              title: Optional[str] = None) -> None:
        """Report tabular output."""


class NullOutput:
    """Output implementation for library callers that do not need display output."""

    def success(self, message: str) -> None:
        """Ignore success output."""

    def error(self, message: str) -> None:
        """Ignore error output."""

    def info(self, message: str) -> None:
        """Ignore informational output."""

    def progress(self, current: int, total: int, message: str) -> None:
        """Ignore progress output."""

    def table(self, headers: List[str], rows: List[List[str]],
              title: Optional[str] = None) -> None:
        """Ignore tabular output."""


__all__ = ["OutputPort", "NullOutput"]

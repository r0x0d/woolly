"""
Progress tracking utilities for dependency analysis.
"""

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)


class ProgressTracker:
    """Tracks progress of dependency tree analysis."""

    def __init__(self, console: Console):
        self.console = console
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("[dim]{task.fields[status]}[/dim]"),
            console=console,
        )
        self.task: TaskID = TaskID(0)
        self.processed = 0
        self.total_discovered = 0

    def start(self, description: str = "Analyzing dependencies") -> None:
        """Start the progress tracker."""
        self.task = self.progress.add_task(
            description, total=None, status="starting..."
        )
        self.progress.start()

    def stop(self) -> None:
        """Stop the progress tracker."""
        self.progress.stop()

    def update(self, package_name: str, discovered: int = 0) -> None:
        """Update progress with current package being checked."""
        self.processed += 1
        self.total_discovered += discovered

        if self.total_discovered > 0:
            self.progress.update(
                self.task,
                completed=self.processed,
                total=self.processed + self.total_discovered,
                status=f"checking: {package_name}",
            )
        else:
            self.progress.update(self.task, status=f"checking: {package_name}")

    def finish(self) -> None:
        """Mark progress as complete."""
        self.progress.update(
            self.task,
            completed=self.processed,
            total=self.processed,
            status="[green]complete![/green]",
        )

"""
Standard output reporter using Rich.

This is the default reporter that outputs to the console with colors and formatting.
"""

from rich import box
from rich.console import Console
from rich.table import Table

from woolly.reporters.base import Reporter, ReportData


class StdoutReporter(Reporter):
    """Reporter that outputs to stdout using Rich formatting."""

    name = "stdout"
    description = "Rich console output (default)"
    file_extension = None
    writes_to_file = False

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def generate(self, data: ReportData) -> str:
        """Generate and print the report to stdout."""
        # Print summary table
        table = Table(
            title=f"Dependency Summary for '{data.root_package}' ({data.language})",
            box=box.ROUNDED,
        )
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        table.add_row("Total dependencies checked", str(data.total_dependencies))
        table.add_row("[green]Packaged in Fedora[/green]", str(data.packaged_count))
        table.add_row("[red]Missing from Fedora[/red]", str(data.missing_count))

        self.console.print(table)
        self.console.print()

        # Print missing packages list
        if data.missing_packages:
            self.console.print("[bold]Missing packages that need packaging:[/bold]")
            for name in sorted(set(data.missing_packages)):
                self.console.print(f"  • {name}")
            self.console.print()

        # Print dependency tree
        self.console.print("[bold]Dependency Tree:[/bold]")
        self.console.print(data.tree)
        self.console.print()

        return ""  # Output is printed directly

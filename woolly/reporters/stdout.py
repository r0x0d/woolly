"""
Standard output reporter using Rich.

This is the default reporter that outputs to the console with colors and formatting.
"""

from rich import box
from rich.console import Console
from rich.table import Table

from woolly.reporters.base import ReportData, Reporter


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

        # Show optional dependency stats if any were found
        if data.optional_total > 0:
            table.add_row("", "")  # Empty row as separator
            table.add_row(
                "[yellow]Optional dependencies[/yellow]", str(data.optional_total)
            )
            table.add_row("[yellow]  ├─ Packaged[/yellow]", str(data.optional_packaged))
            table.add_row("[yellow]  └─ Missing[/yellow]", str(data.optional_missing))

        self.console.print(table)
        self.console.print()

        # Print missing packages list using computed properties
        if data.missing_packages:
            required_missing = data.required_missing_packages
            optional_missing = data.optional_missing_set

            if required_missing:
                self.console.print("[bold]Missing packages that need packaging:[/bold]")
                for name in sorted(required_missing):
                    self.console.print(f"  • {name}")
                self.console.print()

            if optional_missing:
                self.console.print(
                    "[bold yellow]Missing optional packages:[/bold yellow]"
                )
                for name in sorted(optional_missing):
                    self.console.print(f"  • {name} [dim](optional)[/dim]")
                self.console.print()

        # Print dependency tree (skip if missing_only mode is enabled)
        if not data.missing_only:
            self.console.print("[bold]Dependency Tree:[/bold]")
            self.console.print(data.tree)
            self.console.print()

        return ""  # Output is printed directly

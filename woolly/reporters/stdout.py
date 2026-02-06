"""
Standard output reporter using Rich.

This is the default reporter that outputs to the console with colors and formatting.
Uses a grid layout with side-by-side panels on wide terminals (>= 100 cols)
and falls back to stacked layout on narrow terminals.
"""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from woolly.reporters.base import ReportData, Reporter

# Minimum terminal width for side-by-side layout
_MIN_SIDE_BY_SIDE_WIDTH = 100


class StdoutReporter(Reporter):
    """Reporter that outputs to stdout using Rich formatting."""

    name = "stdout"
    description = "Rich console output (default)"
    file_extension = None
    writes_to_file = False

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def _print_side_by_side(self, left, right) -> None:
        """Print two renderables side by side, or stacked on narrow terminals."""
        if self.console.width >= _MIN_SIDE_BY_SIDE_WIDTH:
            grid = Table.grid(padding=(0, 1), expand=True)
            grid.add_column(ratio=1)
            grid.add_column(ratio=1)
            grid.add_row(left, right)
            self.console.print(grid)
        else:
            self.console.print(left)
            self.console.print(right)

    def _build_summary_panel(self, data: ReportData) -> Panel:
        """Build the summary panel with license and dependency stats."""
        table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True)
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        # License row at the top if available
        if data.root_license:
            table.add_row("License", f"[magenta]{data.root_license}[/magenta]")

        table.add_row("Total dependencies", str(data.total_dependencies))
        table.add_row(
            "[green]Packaged in Fedora[/green]", f"[green]{data.packaged_count}[/green]"
        )
        table.add_row(
            "[red]Missing from Fedora[/red]", f"[red]{data.missing_count}[/red]"
        )

        if data.optional_total > 0:
            table.add_row("", "")
            table.add_row(
                "[yellow]Optional dependencies[/yellow]",
                str(data.optional_total),
            )
            table.add_row("[yellow]  Packaged[/yellow]", str(data.optional_packaged))
            table.add_row("[yellow]  Missing[/yellow]", str(data.optional_missing))

        if data.dev_total > 0:
            table.add_row("", "")
            table.add_row("[cyan]Dev dependencies[/cyan]", str(data.dev_total))
            table.add_row("[cyan]  Packaged[/cyan]", str(data.dev_packaged))
            table.add_row("[cyan]  Missing[/cyan]", str(data.dev_missing))

        if data.build_total > 0:
            table.add_row("", "")
            table.add_row("[blue]Build dependencies[/blue]", str(data.build_total))
            table.add_row("[blue]  Packaged[/blue]", str(data.build_packaged))
            table.add_row("[blue]  Missing[/blue]", str(data.build_missing))

        title = f"[bold]Summary for [cyan]{data.root_package}[/cyan] ({data.language})[/bold]"
        return Panel(table, title=title, border_style="green", padding=(0, 1))

    def _build_missing_required_panel(self, data: ReportData) -> Panel:
        """Build the panel for missing required packages."""
        required_missing = data.required_missing_packages
        if required_missing:
            table = Table(box=box.SIMPLE, expand=True, show_header=True)
            table.add_column("Package", style="bold red")
            for name in sorted(required_missing):
                table.add_row(name)
            content = table
        else:
            content = Text("None", style="dim")

        return Panel(
            content,
            title="[bold red]Missing Required[/bold red]",
            border_style="red",
            padding=(0, 1),
        )

    def _build_missing_optional_panel(self, data: ReportData) -> Panel:
        """Build the panel for missing optional packages."""
        optional_missing = data.optional_missing_set
        if optional_missing:
            table = Table(box=box.SIMPLE, expand=True, show_header=True)
            table.add_column("Package", style="bold yellow")
            for name in sorted(optional_missing):
                table.add_row(name)
            content = table
        else:
            content = Text("None", style="dim")

        return Panel(
            content,
            title="[bold yellow]Missing Optional[/bold yellow]",
            border_style="yellow",
            padding=(0, 1),
        )

    def _build_dep_panel(
        self, deps: list[dict], title: str, border_style: str
    ) -> Panel:
        """Build a panel for dev or build dependencies."""
        if deps:
            table = Table(box=box.SIMPLE, expand=True, show_header=True)
            table.add_column("", width=2)  # Status icon
            table.add_column("Package", style="bold")
            table.add_column("Version Req", style="dim")
            table.add_column("Fedora", style="dim")
            for dep in deps:
                icon = "[green]✓[/green]" if dep["is_packaged"] else "[red]✗[/red]"
                fedora_ver = ", ".join(dep.get("fedora_versions", [])) or "-"
                table.add_row(icon, dep["name"], dep["version_requirement"], fedora_ver)
            content = table
        else:
            content = Text("None", style="dim")

        return Panel(content, title=title, border_style=border_style, padding=(0, 1))

    def _build_features_panel(self, data: ReportData) -> Panel:
        """Build the features / extras panel."""
        table = Table(box=box.SIMPLE, expand=True, show_header=True)
        table.add_column("Feature", style="bold magenta")
        table.add_column("Dependencies")

        for feature in data.features:
            deps_str = (
                ", ".join(feature.dependencies)
                if hasattr(feature, "dependencies")
                else ", ".join(feature.get("dependencies", []))
            )
            feature_name = (
                feature.name if hasattr(feature, "name") else feature.get("name", "")
            )
            table.add_row(feature_name, deps_str or "[dim]-[/dim]")

        return Panel(
            table,
            title="[bold magenta]Features / Extras[/bold magenta]",
            border_style="magenta",
            padding=(0, 1),
        )

    def generate(self, data: ReportData) -> str:
        """Generate and print the report to stdout."""
        # ── Summary (full width) ──
        self.console.print(self._build_summary_panel(data))

        # ── Missing packages: Required | Optional (side by side) ──
        if data.missing_packages:
            left = self._build_missing_required_panel(data)
            right = self._build_missing_optional_panel(data)
            self._print_side_by_side(left, right)

        # ── Dev | Build dependencies (side by side) ──
        if data.dev_dependencies or data.build_dependencies:
            left = self._build_dep_panel(
                data.dev_dependencies,
                "[bold cyan]Dev Dependencies[/bold cyan]",
                "cyan",
            )
            right = self._build_dep_panel(
                data.build_dependencies,
                "[bold blue]Build Dependencies[/bold blue]",
                "blue",
            )
            self._print_side_by_side(left, right)

        # ── Features (full width) ──
        if data.features:
            self.console.print(self._build_features_panel(data))

        # ── Dependency Tree (full width, skip if missing_only) ──
        if not data.missing_only:
            self.console.print(
                Panel(
                    data.tree,
                    title="[bold]Dependency Tree[/bold]",
                    border_style="dim",
                    padding=(0, 1),
                )
            )

        return ""  # Output is printed directly

"""
List formats command - display available report formats.
"""

from rich import box
from rich.table import Table

from woolly.commands import app, console
from woolly.reporters import list_reporters


@app.command(name="list-formats")
def list_formats_cmd():
    """List available report formats."""
    table = Table(title="Available Report Formats", box=box.ROUNDED)
    table.add_column("Format", style="bold")
    table.add_column("Description")
    table.add_column("Aliases", style="dim")

    for info in list_reporters():
        alias_str = ", ".join(info.aliases) if info.aliases else "-"
        table.add_row(info.format_id, info.description, alias_str)

    console.print(table)

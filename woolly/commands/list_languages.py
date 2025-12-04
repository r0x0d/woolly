"""
List languages command - display available language providers.
"""

from rich import box
from rich.table import Table

from woolly.commands import app, console
from woolly.languages import get_provider, list_providers


@app.command(name="list-languages")
def list_languages_cmd():
    """List available language providers."""
    table = Table(title="Available Languages", box=box.ROUNDED)
    table.add_column("Language", style="bold")
    table.add_column("Registry")
    table.add_column("Aliases", style="dim")

    for lang_id, display_name, aliases in list_providers():
        provider = get_provider(lang_id)
        registry = provider.registry_name if provider else "Unknown"
        alias_str = ", ".join(aliases) if aliases else "-"
        table.add_row(f"{display_name} ({lang_id})", registry, alias_str)

    console.print(table)

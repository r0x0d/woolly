"""
Clear cache command - clear cached data.
"""

from typing import Annotated

import cyclopts

from woolly.cache import clear_cache
from woolly.commands import app, console


@app.command(name="clear-cache")
def clear_cache_cmd(
    fedora_only: Annotated[
        bool,
        cyclopts.Parameter(
            ("--fedora-only", "-f"),
            negative=(),
            help="Clear only Fedora repoquery cache.",
        ),
    ] = False,
):
    """Clear cached data.

    Parameters
    ----------
    fedora_only
        If set, only clear the Fedora repoquery cache.
    """
    if fedora_only:
        cleared = clear_cache("fedora")
        if cleared:
            console.print("[yellow]Cleared Fedora cache[/yellow]")
        else:
            console.print("[yellow]No Fedora cache to clear[/yellow]")
    else:
        cleared = clear_cache()
        if cleared:
            console.print(f"[yellow]Cleared caches: {', '.join(cleared)}[/yellow]")
        else:
            console.print("[yellow]No cache to clear[/yellow]")

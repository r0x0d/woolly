"""
CLI commands for Woolly.

This module defines the cyclopts app and registers all commands.
"""

import cyclopts
from rich.console import Console

# Shared console instance for all commands
console = Console()

# Main application
app = cyclopts.App(
    name="woolly",
    help="Check if package dependencies are available in Fedora.",
    version_flags=(),  # We don't need --version for the app itself
)

# Import and register commands
# These imports must come after app is defined to avoid circular imports
from woolly.commands.check import check  # noqa: E402, F401
from woolly.commands.clear_cache import clear_cache_cmd  # noqa: E402, F401
from woolly.commands.list_formats import list_formats_cmd  # noqa: E402, F401
from woolly.commands.list_languages import list_languages_cmd  # noqa: E402, F401

__all__ = ["app", "console"]

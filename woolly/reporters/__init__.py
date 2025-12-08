"""
Report generators registry.

This module provides automatic discovery and registration of report generators.
To add a new format, create a module in this directory that defines a class
inheriting from Reporter and add it to REPORTERS dict.
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from rich.console import Console

from woolly.reporters.base import ReportData, Reporter, strip_markup
from woolly.reporters.json import JsonReporter
from woolly.reporters.markdown import MarkdownReporter
from woolly.reporters.stdout import StdoutReporter
from woolly.reporters.template import TemplateReporter


class ReporterInfo(BaseModel):
    """Information about an available reporter."""

    format_id: str
    description: str
    aliases: list[str] = Field(default_factory=list)


# Registry of available reporters
# Key: format identifier (used in CLI)
# Value: Reporter class
REPORTERS: dict[str, type[Reporter]] = {
    "stdout": StdoutReporter,
    "markdown": MarkdownReporter,
    "json": JsonReporter,
    "template": TemplateReporter,
}

# Aliases for convenience
ALIASES: dict[str, str] = {
    "md": "markdown",
    "console": "stdout",
    "terminal": "stdout",
    "tpl": "template",
    "jinja": "template",
    "jinja2": "template",
}


def get_reporter(
    format_name: str,
    console: Optional[Console] = None,
    template_path: Optional[Path] = None,
) -> Optional[Reporter]:
    """
    Get an instantiated reporter for the specified format.

    Args:
        format_name: Format identifier or alias (e.g., "json", "markdown", "md")
        console: Console instance for stdout reporter.
        template_path: Path to template file for template reporter.

    Returns:
        Instantiated Reporter, or None if not found.
    """
    # Resolve aliases
    format_name = format_name.lower()
    if format_name in ALIASES:
        format_name = ALIASES[format_name]

    reporter_class = REPORTERS.get(format_name)
    if reporter_class is None:
        return None

    # StdoutReporter needs a console
    if format_name == "stdout" and console:
        return StdoutReporter(console=console)

    # TemplateReporter needs a template path
    if format_name == "template":
        return TemplateReporter(template_path=template_path)

    return reporter_class()


def list_reporters() -> list[ReporterInfo]:
    """
    List all available reporters.

    Returns:
        List of ReporterInfo objects with format details.
    """
    result = []
    for format_id, reporter_class in REPORTERS.items():
        # Find aliases for this format
        aliases = [alias for alias, target in ALIASES.items() if target == format_id]
        result.append(
            ReporterInfo(
                format_id=format_id,
                description=reporter_class.description,
                aliases=aliases,
            )
        )
    return result


def get_available_formats() -> list[str]:
    """Get list of available format identifiers."""
    return list(REPORTERS.keys())


__all__ = [
    "Reporter",
    "ReportData",
    "ReporterInfo",
    "StdoutReporter",
    "MarkdownReporter",
    "JsonReporter",
    "TemplateReporter",
    "get_reporter",
    "list_reporters",
    "get_available_formats",
    "strip_markup",
]

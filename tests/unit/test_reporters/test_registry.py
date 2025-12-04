"""
Unit tests for woolly.reporters registry module.

Tests cover:
- Good path: reporter lookup, listing
- Critical path: alias resolution
- Bad path: unknown reporters
"""

import pytest
from rich.console import Console

from woolly.reporters import (
    ALIASES,
    REPORTERS,
    JsonReporter,
    MarkdownReporter,
    ReporterInfo,
    StdoutReporter,
    get_available_formats,
    get_reporter,
    list_reporters,
)


class TestReporterRegistry:
    """Tests for reporter registry constants."""

    @pytest.mark.unit
    def test_stdout_registered(self):
        """Good path: stdout reporter is registered."""
        assert "stdout" in REPORTERS
        assert REPORTERS["stdout"] == StdoutReporter

    @pytest.mark.unit
    def test_json_registered(self):
        """Good path: JSON reporter is registered."""
        assert "json" in REPORTERS
        assert REPORTERS["json"] == JsonReporter

    @pytest.mark.unit
    def test_markdown_registered(self):
        """Good path: Markdown reporter is registered."""
        assert "markdown" in REPORTERS
        assert REPORTERS["markdown"] == MarkdownReporter

    @pytest.mark.unit
    def test_aliases_defined(self):
        """Good path: aliases are defined."""
        assert "md" in ALIASES
        assert "console" in ALIASES
        assert ALIASES["md"] == "markdown"
        assert ALIASES["console"] == "stdout"


class TestGetReporter:
    """Tests for get_reporter function."""

    @pytest.mark.unit
    def test_get_stdout_reporter(self):
        """Good path: returns stdout reporter."""
        console = Console()
        reporter = get_reporter("stdout", console=console)

        assert isinstance(reporter, StdoutReporter)
        assert reporter.console is console

    @pytest.mark.unit
    def test_get_json_reporter(self):
        """Good path: returns JSON reporter."""
        reporter = get_reporter("json")

        assert isinstance(reporter, JsonReporter)

    @pytest.mark.unit
    def test_get_markdown_reporter(self):
        """Good path: returns Markdown reporter."""
        reporter = get_reporter("markdown")

        assert isinstance(reporter, MarkdownReporter)

    @pytest.mark.unit
    def test_alias_resolution(self):
        """Critical path: resolves aliases correctly."""
        assert isinstance(get_reporter("md"), MarkdownReporter)
        assert isinstance(get_reporter("console"), StdoutReporter)
        assert isinstance(get_reporter("terminal"), StdoutReporter)

    @pytest.mark.unit
    def test_case_insensitive(self):
        """Good path: format lookup is case-insensitive."""
        assert isinstance(get_reporter("JSON"), JsonReporter)
        assert isinstance(get_reporter("Markdown"), MarkdownReporter)

    @pytest.mark.unit
    def test_returns_none_for_unknown(self):
        """Bad path: returns None for unknown format."""
        reporter = get_reporter("unknown-format")

        assert reporter is None

    @pytest.mark.unit
    def test_stdout_without_console(self):
        """Good path: stdout reporter works without console."""
        reporter = get_reporter("stdout")

        assert isinstance(reporter, StdoutReporter)


class TestListReporters:
    """Tests for list_reporters function."""

    @pytest.mark.unit
    def test_returns_list_of_reporter_info(self):
        """Good path: returns list of ReporterInfo models."""
        reporters = list_reporters()

        assert isinstance(reporters, list)
        assert len(reporters) >= 3  # At least stdout, json, markdown

        for item in reporters:
            assert isinstance(item, ReporterInfo)

    @pytest.mark.unit
    def test_includes_stdout(self):
        """Good path: includes stdout reporter."""
        reporters = list_reporters()

        stdout_entry = next((r for r in reporters if r.format_id == "stdout"), None)
        assert stdout_entry is not None
        assert "console" in stdout_entry.aliases

    @pytest.mark.unit
    def test_includes_json(self):
        """Good path: includes JSON reporter."""
        reporters = list_reporters()

        json_entry = next((r for r in reporters if r.format_id == "json"), None)
        assert json_entry is not None

    @pytest.mark.unit
    def test_includes_markdown(self):
        """Good path: includes Markdown reporter."""
        reporters = list_reporters()

        md_entry = next((r for r in reporters if r.format_id == "markdown"), None)
        assert md_entry is not None
        assert "md" in md_entry.aliases


class TestGetAvailableFormats:
    """Tests for get_available_formats function."""

    @pytest.mark.unit
    def test_returns_list(self):
        """Good path: returns list of strings."""
        formats = get_available_formats()

        assert isinstance(formats, list)
        assert all(isinstance(fmt, str) for fmt in formats)

    @pytest.mark.unit
    def test_includes_all_reporters(self):
        """Good path: includes all registered reporters."""
        formats = get_available_formats()

        assert "stdout" in formats
        assert "json" in formats
        assert "markdown" in formats

    @pytest.mark.unit
    def test_does_not_include_aliases(self):
        """Good path: does not include aliases."""
        formats = get_available_formats()

        assert "md" not in formats
        assert "console" not in formats

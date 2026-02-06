"""
Unit tests for woolly.reporters.stdout module.

Tests cover:
- Good path: stdout output generation
- Critical path: console printing
"""

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from woolly.reporters.stdout import StdoutReporter


class TestStdoutReporterAttributes:
    """Tests for StdoutReporter class attributes."""

    @pytest.mark.unit
    def test_attributes(self):
        """Good path: reporter has correct attributes."""
        reporter = StdoutReporter()

        assert reporter.name == "stdout"
        assert reporter.file_extension is None
        assert reporter.writes_to_file is False


class TestStdoutReporterInit:
    """Tests for StdoutReporter initialization."""

    @pytest.mark.unit
    def test_accepts_console(self):
        """Good path: accepts custom console."""
        console = Console()
        reporter = StdoutReporter(console=console)

        assert reporter.console is console

    @pytest.mark.unit
    def test_creates_default_console(self):
        """Good path: creates default console if not provided."""
        reporter = StdoutReporter()

        assert reporter.console is not None
        assert isinstance(reporter.console, Console)


def _get_printed_objects(mock_console):
    """Extract all objects passed to mock_console.print()."""
    objects = []
    for call_obj in mock_console.print.call_args_list:
        args = call_obj[0] if call_obj[0] else []
        objects.extend(args)
    return objects


def _stringify_printed(mock_console):
    """Convert all print calls to a single string for text matching."""
    parts = []
    for obj in _get_printed_objects(mock_console):
        parts.append(str(obj))
    return " ".join(parts)


class TestStdoutReporterGenerate:
    """Tests for StdoutReporter.generate method."""

    @pytest.mark.unit
    def test_prints_summary_panel(self, sample_report_data, mock_console):
        """Good path: prints summary panel."""
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # Verify print was called (summary panel + missing panels + tree panel)
        assert mock_console.print.call_count >= 1

        # First call should be the summary panel
        first_arg = mock_console.print.call_args_list[0][0][0]
        assert isinstance(first_arg, Panel)

    @pytest.mark.unit
    def test_prints_missing_packages(self, sample_report_data, mock_console):
        """Good path: prints missing packages as side-by-side panels."""
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # The side-by-side layout produces a grid Table or two Panels
        printed = _get_printed_objects(mock_console)
        # With missing packages, we should have at least the summary + grid/panels + tree
        assert len(printed) >= 2

    @pytest.mark.unit
    def test_prints_tree_in_panel(self, sample_report_data, mock_console):
        """Good path: prints dependency tree inside a Panel."""
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # Last printed object should be the tree panel
        printed = _get_printed_objects(mock_console)
        last_panel = printed[-1]
        assert isinstance(last_panel, Panel)

    @pytest.mark.unit
    def test_returns_empty_string(self, sample_report_data, mock_console):
        """Good path: returns empty string (output is printed)."""
        reporter = StdoutReporter(console=mock_console)

        result = reporter.generate(sample_report_data)

        assert result == ""

    @pytest.mark.unit
    def test_no_missing_panels_when_empty(self, sample_report_data, mock_console):
        """Good path: doesn't print missing panels when no missing packages."""
        sample_report_data.missing_packages = []
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # Should only have summary panel + tree panel (no missing panels)
        printed = _get_printed_objects(mock_console)
        assert len(printed) == 2  # summary + tree

    @pytest.mark.unit
    def test_missing_only_skips_dependency_tree(self, sample_report_data, mock_console):
        """Good path: skips dependency tree when missing_only is True."""
        sample_report_data.missing_only = True
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # Should not print Dependency Tree panel
        output = _stringify_printed(mock_console)
        assert "Dependency Tree" not in output

    @pytest.mark.unit
    def test_missing_only_false_shows_dependency_tree(
        self, sample_report_data, mock_console
    ):
        """Good path: shows dependency tree when missing_only is False."""
        sample_report_data.missing_only = False
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # Last printed object should be the tree Panel with "Dependency Tree" title
        printed = _get_printed_objects(mock_console)
        last = printed[-1]
        assert isinstance(last, Panel)
        assert "Dependency Tree" in str(last.title)


class TestStdoutReporterSideBySide:
    """Tests for the side-by-side layout behavior."""

    @pytest.mark.unit
    def test_wide_terminal_uses_grid(self, sample_report_data, mock_console):
        """Good path: wide terminal renders side-by-side as a grid."""
        mock_console.width = 120
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # With wide terminal and missing packages, the missing section
        # is rendered as a single grid Table (not two separate Panels)
        printed = _get_printed_objects(mock_console)
        grid_found = any(isinstance(obj, Table) for obj in printed)
        assert grid_found

    @pytest.mark.unit
    def test_narrow_terminal_stacks_panels(self, sample_report_data, mock_console):
        """Good path: narrow terminal stacks panels vertically."""
        mock_console.width = 80  # Below threshold
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # With narrow terminal and missing packages, panels are printed separately
        printed = _get_printed_objects(mock_console)
        panel_count = sum(1 for obj in printed if isinstance(obj, Panel))
        # summary + missing_required + missing_optional + tree = 4 panels
        assert panel_count == 4

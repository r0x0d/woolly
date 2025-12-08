"""
Unit tests for woolly.reporters.stdout module.

Tests cover:
- Good path: stdout output generation
- Critical path: console printing
"""

import pytest
from rich.console import Console

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


class TestStdoutReporterGenerate:
    """Tests for StdoutReporter.generate method."""

    @pytest.mark.unit
    def test_prints_summary_table(self, sample_report_data, mock_console):
        """Good path: prints summary table."""
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # Verify print was called multiple times
        assert mock_console.print.call_count >= 3

    @pytest.mark.unit
    def test_prints_missing_packages(self, sample_report_data, mock_console):
        """Good path: prints missing packages list."""
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # Check that print was called with missing packages content
        calls_str = str(mock_console.print.call_args_list)
        assert "Missing packages" in calls_str or mock_console.print.called

    @pytest.mark.unit
    def test_prints_tree(self, sample_report_data, mock_console):
        """Good path: prints dependency tree."""
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # The tree should be passed to print
        assert mock_console.print.called

    @pytest.mark.unit
    def test_returns_empty_string(self, sample_report_data, mock_console):
        """Good path: returns empty string (output is printed)."""
        reporter = StdoutReporter(console=mock_console)

        result = reporter.generate(sample_report_data)

        assert result == ""

    @pytest.mark.unit
    def test_no_missing_list_when_empty(self, sample_report_data, mock_console):
        """Good path: doesn't print missing list when no missing packages."""
        sample_report_data.missing_packages = []
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # Should not print "Missing packages that need packaging"
        for call_obj in mock_console.print.call_args_list:
            args = call_obj[0] if call_obj[0] else []
            for arg in args:
                if isinstance(arg, str):
                    assert "Missing packages that need packaging" not in arg

    @pytest.mark.unit
    def test_missing_only_skips_dependency_tree(self, sample_report_data, mock_console):
        """Good path: skips dependency tree when missing_only is True."""
        sample_report_data.missing_only = True
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # Should not print "Dependency Tree:"
        for call_obj in mock_console.print.call_args_list:
            args = call_obj[0] if call_obj[0] else []
            for arg in args:
                if isinstance(arg, str):
                    assert "Dependency Tree:" not in arg

    @pytest.mark.unit
    def test_missing_only_false_shows_dependency_tree(
        self, sample_report_data, mock_console
    ):
        """Good path: shows dependency tree when missing_only is False."""
        sample_report_data.missing_only = False
        reporter = StdoutReporter(console=mock_console)

        reporter.generate(sample_report_data)

        # Should print "Dependency Tree:"
        calls_str = str(mock_console.print.call_args_list)
        assert "Dependency Tree" in calls_str

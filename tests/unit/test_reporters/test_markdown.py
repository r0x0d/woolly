"""
Unit tests for woolly.reporters.markdown module.

Tests cover:
- Good path: Markdown generation
- Critical path: proper formatting, tree rendering
"""

import pytest

from woolly.reporters.markdown import MarkdownReporter


class TestMarkdownReporterAttributes:
    """Tests for MarkdownReporter class attributes."""

    @pytest.mark.unit
    def test_attributes(self):
        """Good path: reporter has correct attributes."""
        reporter = MarkdownReporter()

        assert reporter.name == "markdown"
        assert reporter.file_extension == "md"
        assert reporter.writes_to_file is True


class TestMarkdownReporterGenerate:
    """Tests for MarkdownReporter.generate method."""

    @pytest.mark.unit
    def test_includes_title(self, sample_report_data):
        """Good path: includes title with package name."""
        reporter = MarkdownReporter()

        result = reporter.generate(sample_report_data)

        assert "# Dependency Report: test-package" in result

    @pytest.mark.unit
    def test_includes_metadata(self, sample_report_data):
        """Good path: includes metadata section."""
        reporter = MarkdownReporter()

        result = reporter.generate(sample_report_data)

        assert "**Generated:**" in result
        assert "**Language:** Rust" in result
        assert "**Registry:** crates.io" in result

    @pytest.mark.unit
    def test_includes_version_when_provided(self, sample_report_data):
        """Good path: includes version when specified."""
        reporter = MarkdownReporter()

        result = reporter.generate(sample_report_data)

        assert "**Version:** 1.0.0" in result

    @pytest.mark.unit
    def test_includes_summary_table(self, sample_report_data):
        """Good path: includes summary table."""
        reporter = MarkdownReporter()

        result = reporter.generate(sample_report_data)

        assert "## Summary" in result
        assert "| Metric | Value |" in result
        assert "| Total dependencies checked | 5 |" in result
        assert "| Packaged in Fedora | 3 |" in result
        assert "| Missing from Fedora | 2 |" in result

    @pytest.mark.unit
    def test_includes_missing_packages(self, sample_report_data):
        """Good path: includes missing packages section."""
        reporter = MarkdownReporter()

        result = reporter.generate(sample_report_data)

        assert "## Missing Packages" in result
        assert "- `missing-a`" in result
        assert "- `missing-b`" in result

    @pytest.mark.unit
    def test_includes_packaged_packages(self, sample_report_data):
        """Good path: includes packaged packages section."""
        reporter = MarkdownReporter()

        result = reporter.generate(sample_report_data)

        assert "## Packaged Packages" in result
        assert "- `packaged-a`" in result

    @pytest.mark.unit
    def test_includes_dependency_tree(self, sample_report_data):
        """Good path: includes dependency tree in code block."""
        reporter = MarkdownReporter()

        result = reporter.generate(sample_report_data)

        assert "## Dependency Tree" in result
        assert "```" in result

    @pytest.mark.unit
    def test_no_missing_section_when_empty(self, sample_report_data):
        """Good path: no missing section when no missing packages."""
        sample_report_data.missing_packages = []
        reporter = MarkdownReporter()

        result = reporter.generate(sample_report_data)

        assert "## Missing Packages" not in result

    @pytest.mark.unit
    def test_no_packaged_section_when_empty(self, sample_report_data):
        """Good path: no packaged section when no packaged packages."""
        sample_report_data.packaged_packages = []
        reporter = MarkdownReporter()

        result = reporter.generate(sample_report_data)

        assert "## Packaged Packages" not in result


class TestMarkdownReporterTreeToText:
    """Tests for MarkdownReporter._tree_to_text method."""

    @pytest.mark.unit
    def test_renders_tree_structure(self, sample_tree):
        """Good path: renders tree with proper characters."""
        reporter = MarkdownReporter()

        result = reporter._tree_to_text(sample_tree)

        # Should contain tree structure characters
        assert "├──" in result or "└──" in result

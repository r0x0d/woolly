"""
Unit tests for woolly.reporters.json module.

Tests cover:
- Good path: JSON generation
- Critical path: tree parsing, metadata structure
"""

import json

import pytest

from woolly.reporters.json import JsonReporter, TreeNodeData


class TestJsonReporterAttributes:
    """Tests for JsonReporter class attributes."""

    @pytest.mark.unit
    def test_attributes(self):
        """Good path: reporter has correct attributes."""
        reporter = JsonReporter()

        assert reporter.name == "json"
        assert reporter.file_extension == "json"
        assert reporter.writes_to_file is True


class TestJsonReporterGenerate:
    """Tests for JsonReporter.generate method."""

    @pytest.mark.unit
    def test_returns_valid_json(self, sample_report_data):
        """Good path: returns valid JSON string."""
        reporter = JsonReporter()

        result = reporter.generate(sample_report_data)

        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.unit
    def test_includes_metadata(self, sample_report_data):
        """Good path: includes metadata section."""
        reporter = JsonReporter()

        result = reporter.generate(sample_report_data)
        parsed = json.loads(result)

        assert "metadata" in parsed
        assert parsed["metadata"]["tool"] == "woolly"
        assert parsed["metadata"]["root_package"] == "test-package"
        assert parsed["metadata"]["language"] == "Rust"
        assert parsed["metadata"]["registry"] == "crates.io"

    @pytest.mark.unit
    def test_includes_summary(self, sample_report_data):
        """Good path: includes summary section."""
        reporter = JsonReporter()

        result = reporter.generate(sample_report_data)
        parsed = json.loads(result)

        assert "summary" in parsed
        assert parsed["summary"]["total_dependencies"] == 5
        assert parsed["summary"]["packaged_count"] == 3
        assert parsed["summary"]["missing_count"] == 2

    @pytest.mark.unit
    def test_includes_package_lists(self, sample_report_data):
        """Good path: includes sorted package lists."""
        reporter = JsonReporter()

        result = reporter.generate(sample_report_data)
        parsed = json.loads(result)

        assert "missing_packages" in parsed
        assert "packaged_packages" in parsed
        assert parsed["missing_packages"] == ["missing-a", "missing-b"]

    @pytest.mark.unit
    def test_includes_dependency_tree(self, sample_report_data):
        """Good path: includes dependency tree."""
        reporter = JsonReporter()

        result = reporter.generate(sample_report_data)
        parsed = json.loads(result)

        assert "dependency_tree" in parsed
        assert isinstance(parsed["dependency_tree"], dict)

    @pytest.mark.unit
    def test_timestamp_is_iso_format(self, sample_report_data):
        """Good path: timestamp is in ISO format."""
        reporter = JsonReporter()

        result = reporter.generate(sample_report_data)
        parsed = json.loads(result)

        timestamp = parsed["metadata"]["generated_at"]
        assert "2024-01-15" in timestamp


class TestJsonReporterParseLabel:
    """Tests for JsonReporter._parse_label method."""

    @pytest.fixture
    def reporter(self):
        return JsonReporter()

    @pytest.mark.unit
    def test_returns_tree_node_data_model(self, reporter):
        """Good path: returns TreeNodeData model."""
        label = "[bold]test[/bold]"

        result = reporter._parse_label(label)

        assert isinstance(result, TreeNodeData)

    @pytest.mark.unit
    def test_parses_packaged_label(self, reporter):
        """Good path: parses packaged package label."""
        # Note: Rich markup like [dim cyan] gets stripped, so package names
        # in brackets are only detected if they're literal brackets
        label = "[bold]serde[/bold] [dim]v1.0.200[/dim] • [green]✓ packaged[/green] [dim](1.0.200)[/dim]"

        result = reporter._parse_label(label)

        assert result.name == "serde"
        assert result.version == "1.0.200"
        assert result.status == "packaged"
        assert "1.0.200" in result.fedora_versions

    @pytest.mark.unit
    def test_parses_not_packaged_label(self, reporter):
        """Good path: parses not packaged package label."""
        label = "[bold]missing-pkg[/bold] [dim]v2.0.0[/dim] • [red]✗ not packaged[/red]"

        result = reporter._parse_label(label)

        assert result.name == "missing-pkg"
        assert result.status == "not_packaged"

    @pytest.mark.unit
    def test_parses_visited_label(self, reporter):
        """Good path: parses already visited label."""
        label = "[dim]serde[/dim] [dim]v1.0.0[/dim] • [green]✓[/green] [dim](already visited)[/dim]"

        result = reporter._parse_label(label)

        assert result.status == "visited"
        assert result.is_packaged is True

    @pytest.mark.unit
    def test_parses_not_found_label(self, reporter):
        """Good path: parses not found label."""
        label = "[bold red]unknown-pkg[/bold red] • [red]not found on crates.io[/red]"

        result = reporter._parse_label(label)

        assert result.status == "not_found"

    @pytest.mark.unit
    def test_parses_max_depth_label(self, reporter):
        """Good path: parses max depth reached label."""
        label = "[dim]deep-pkg (max depth reached)[/dim]"

        result = reporter._parse_label(label)

        assert result.status == "max_depth_reached"

    @pytest.mark.unit
    def test_strips_rich_markup(self, reporter):
        """Critical path: strips all Rich markup from raw."""
        label = "[bold][red]test[/red][/bold]"

        result = reporter._parse_label(label)

        assert "[" not in result.raw
        assert "]" not in result.raw


class TestJsonReporterMissingOnly:
    """Tests for JsonReporter with missing_only flag."""

    @pytest.mark.unit
    def test_missing_only_metadata_included(self, sample_report_data):
        """Good path: missing_only is included in metadata."""
        sample_report_data.missing_only = True
        reporter = JsonReporter()

        result = reporter.generate(sample_report_data)
        parsed = json.loads(result)

        assert "missing_only" in parsed["metadata"]
        assert parsed["metadata"]["missing_only"] is True

    @pytest.mark.unit
    def test_missing_only_excludes_packaged_packages(self, sample_report_data):
        """Good path: excludes packaged packages when missing_only is True."""
        sample_report_data.missing_only = True
        reporter = JsonReporter()

        result = reporter.generate(sample_report_data)
        parsed = json.loads(result)

        assert parsed["packaged_packages"] == []

    @pytest.mark.unit
    def test_missing_only_false_includes_packaged_packages(self, sample_report_data):
        """Good path: includes packaged packages when missing_only is False."""
        sample_report_data.missing_only = False
        reporter = JsonReporter()

        result = reporter.generate(sample_report_data)
        parsed = json.loads(result)

        assert len(parsed["packaged_packages"]) > 0
        assert "packaged-a" in parsed["packaged_packages"]

    @pytest.mark.unit
    def test_missing_only_still_includes_missing_packages(self, sample_report_data):
        """Good path: missing packages are still included when missing_only is True."""
        sample_report_data.missing_only = True
        reporter = JsonReporter()

        result = reporter.generate(sample_report_data)
        parsed = json.loads(result)

        assert len(parsed["missing_packages"]) > 0
        assert "missing-a" in parsed["missing_packages"]

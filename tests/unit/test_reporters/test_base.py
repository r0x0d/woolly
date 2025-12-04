"""
Unit tests for woolly.reporters.base module.

Tests cover:
- Good path: ReportData creation, Reporter base class
- Critical path: file output generation
"""

from datetime import datetime

import pytest
from rich.tree import Tree

from woolly.reporters.base import Reporter, ReportData, strip_markup


class TestReportData:
    """Tests for ReportData model."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Good path: ReportData with required fields."""
        tree = Tree("root")
        data = ReportData(
            root_package="test",
            language="Rust",
            registry="crates.io",
            total_dependencies=10,
            packaged_count=8,
            missing_count=2,
            tree=tree,
        )

        assert data.root_package == "test"
        assert data.language == "Rust"
        assert data.total_dependencies == 10

    @pytest.mark.unit
    def test_default_values(self):
        """Good path: default values are correct."""
        tree = Tree("root")
        data = ReportData(
            root_package="test",
            language="Rust",
            registry="crates.io",
            total_dependencies=0,
            packaged_count=0,
            missing_count=0,
            tree=tree,
        )

        assert data.missing_packages == []
        assert data.packaged_packages == []
        assert data.max_depth == 50
        assert data.version is None
        assert isinstance(data.timestamp, datetime)

    @pytest.mark.unit
    def test_timestamp_is_set(self):
        """Good path: timestamp is set to current time by default."""
        tree = Tree("root")
        before = datetime.now()
        data = ReportData(
            root_package="test",
            language="Rust",
            registry="crates.io",
            total_dependencies=0,
            packaged_count=0,
            missing_count=0,
            tree=tree,
        )
        after = datetime.now()

        assert before <= data.timestamp <= after

    @pytest.mark.unit
    def test_required_missing_packages_property(self):
        """Good path: required_missing_packages computed property works."""
        tree = Tree("root")
        data = ReportData(
            root_package="test",
            language="Rust",
            registry="crates.io",
            total_dependencies=3,
            packaged_count=1,
            missing_count=2,
            missing_packages=["pkg-a", "pkg-b", "optional-pkg"],
            optional_missing_packages=["optional-pkg"],
            tree=tree,
        )

        assert data.required_missing_packages == {"pkg-a", "pkg-b"}

    @pytest.mark.unit
    def test_optional_missing_set_property(self):
        """Good path: optional_missing_set computed property works."""
        tree = Tree("root")
        data = ReportData(
            root_package="test",
            language="Rust",
            registry="crates.io",
            total_dependencies=2,
            packaged_count=0,
            missing_count=2,
            optional_missing_packages=["opt-a", "opt-b"],
            tree=tree,
        )

        assert data.optional_missing_set == {"opt-a", "opt-b"}

    @pytest.mark.unit
    def test_unique_packaged_packages_property(self):
        """Good path: unique_packaged_packages computed property works."""
        tree = Tree("root")
        data = ReportData(
            root_package="test",
            language="Rust",
            registry="crates.io",
            total_dependencies=3,
            packaged_count=3,
            missing_count=0,
            packaged_packages=["pkg-a", "pkg-b", "pkg-a"],  # duplicates
            tree=tree,
        )

        assert data.unique_packaged_packages == {"pkg-a", "pkg-b"}


class TestStripMarkup:
    """Tests for strip_markup utility function."""

    @pytest.mark.unit
    def test_strips_bold_tags(self):
        """Good path: strips bold tags."""
        result = strip_markup("[bold]text[/bold]")
        assert result == "text"

    @pytest.mark.unit
    def test_strips_color_tags(self):
        """Good path: strips color tags."""
        result = strip_markup("[red]error[/red] and [green]success[/green]")
        assert result == "error and success"

    @pytest.mark.unit
    def test_strips_nested_tags(self):
        """Good path: strips nested tags."""
        result = strip_markup("[bold][red]important[/red][/bold]")
        assert result == "important"

    @pytest.mark.unit
    def test_preserves_plain_text(self):
        """Good path: preserves text without markup."""
        result = strip_markup("plain text")
        assert result == "plain text"


class ConcreteReporter(Reporter):
    """Concrete reporter for testing abstract base class."""

    name = "test"
    description = "Test reporter"
    file_extension = "txt"
    writes_to_file = True

    def generate(self, data: ReportData) -> str:
        return f"Report for {data.root_package}"


class TestReporterGetOutputFilename:
    """Tests for Reporter.get_output_filename method."""

    @pytest.mark.unit
    def test_includes_package_name(self, sample_report_data):
        """Good path: filename includes package name."""
        reporter = ConcreteReporter()

        filename = reporter.get_output_filename(sample_report_data)

        assert "test-package" in filename

    @pytest.mark.unit
    def test_includes_timestamp(self, sample_report_data):
        """Good path: filename includes timestamp."""
        reporter = ConcreteReporter()

        filename = reporter.get_output_filename(sample_report_data)

        # Should contain date format YYYYMMDD
        assert "20240115" in filename

    @pytest.mark.unit
    def test_includes_extension(self, sample_report_data):
        """Good path: filename includes file extension."""
        reporter = ConcreteReporter()

        filename = reporter.get_output_filename(sample_report_data)

        assert filename.endswith(".txt")

    @pytest.mark.unit
    def test_starts_with_woolly(self, sample_report_data):
        """Good path: filename starts with woolly prefix."""
        reporter = ConcreteReporter()

        filename = reporter.get_output_filename(sample_report_data)

        assert filename.startswith("woolly_")


class TestReporterTreeMethods:
    """Tests for Reporter tree traversal methods."""

    @pytest.mark.unit
    def test_get_label_from_string(self):
        """Good path: _get_label returns string directly."""
        reporter = ConcreteReporter()

        result = reporter._get_label("plain string")

        assert result == "plain string"

    @pytest.mark.unit
    def test_get_label_from_tree(self):
        """Good path: _get_label extracts label from Tree."""
        reporter = ConcreteReporter()
        tree = Tree("root label")

        result = reporter._get_label(tree)

        assert result == "root label"

    @pytest.mark.unit
    def test_get_children_returns_list(self):
        """Good path: _get_children returns list of children."""
        reporter = ConcreteReporter()
        tree = Tree("root")
        tree.add("child1")
        tree.add("child2")

        result = reporter._get_children(tree)

        assert len(result) == 2


class TestReporterWriteReport:
    """Tests for Reporter.write_report method."""

    @pytest.mark.unit
    def test_writes_file(self, sample_report_data, tmp_path):
        """Good path: writes report to file."""
        reporter = ConcreteReporter()

        output_path = reporter.write_report(sample_report_data, tmp_path)

        assert output_path is not None
        assert output_path.exists()
        assert output_path.read_text() == "Report for test-package"

    @pytest.mark.unit
    def test_uses_current_dir_by_default(
        self, sample_report_data, monkeypatch, tmp_path
    ):
        """Good path: uses current directory when no output_dir specified."""
        reporter = ConcreteReporter()
        monkeypatch.chdir(tmp_path)

        output_path = reporter.write_report(sample_report_data)

        assert output_path is not None
        assert output_path.parent == tmp_path

    @pytest.mark.unit
    def test_returns_none_for_stdout_reporter(self, sample_report_data, tmp_path):
        """Good path: returns None for non-file reporters."""

        class StdoutOnlyReporter(Reporter):
            name = "stdout"
            description = "Stdout"
            writes_to_file = False

            def generate(self, data):
                return "output"

        reporter = StdoutOnlyReporter()

        result = reporter.write_report(sample_report_data, tmp_path)

        assert result is None

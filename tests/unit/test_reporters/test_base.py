"""
Unit tests for woolly.reporters.base module.

Tests cover:
- Good path: ReportData creation, Reporter base class
- Critical path: file output generation
"""

from datetime import datetime

import pytest
from rich.tree import Tree

from woolly.reporters.base import PackageStatus, Reporter, ReportData


class TestPackageStatus:
    """Tests for PackageStatus model."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Good path: PackageStatus with required fields."""
        status = PackageStatus(name="test-pkg", is_packaged=True)

        assert status.name == "test-pkg"
        assert status.is_packaged is True

    @pytest.mark.unit
    def test_default_values(self):
        """Good path: default values are correct."""
        status = PackageStatus(name="test", is_packaged=False)

        assert status.version is None
        assert status.fedora_versions == []
        assert status.fedora_packages == []
        assert status.is_visited is False
        assert status.not_found is False

    @pytest.mark.unit
    def test_all_fields(self):
        """Good path: all fields can be set."""
        status = PackageStatus(
            name="serde",
            version="1.0.200",
            is_packaged=True,
            fedora_versions=["1.0.0", "1.0.200"],
            fedora_packages=["rust-serde"],
            is_visited=True,
            not_found=False,
        )

        assert status.version == "1.0.200"
        assert "1.0.200" in status.fedora_versions


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
        assert data.packages == []
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

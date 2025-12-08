"""Unit tests for the template reporter."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from woolly.reporters.base import ReportData
from woolly.reporters.template import TemplateReporter


@pytest.fixture
def sample_report_data():
    """Create sample report data for testing."""
    mock_tree = MagicMock()
    mock_tree.label = "test-package v1.0.0 • ✓ packaged"
    mock_tree.children = []

    return ReportData(
        root_package="test-package",
        language="Rust",
        registry="crates.io",
        total_dependencies=10,
        packaged_count=7,
        missing_count=3,
        missing_packages=["missing1", "missing2", "missing3"],
        packaged_packages=["packaged1", "packaged2", "packaged3"],
        tree=mock_tree,
        max_depth=50,
        version="1.0.0",
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        include_optional=True,
        optional_total=2,
        optional_packaged=1,
        optional_missing=1,
        optional_missing_packages=["missing3"],
        missing_only=False,
    )


class TestTemplateReporter:
    """Tests for TemplateReporter class."""

    def test_name_and_description(self):
        """Test reporter name and description."""
        reporter = TemplateReporter()
        assert reporter.name == "template"
        assert "template" in reporter.description.lower()
        assert reporter.file_extension == "md"
        assert reporter.writes_to_file is True

    def test_init_without_template_path(self):
        """Test initialization without template path."""
        reporter = TemplateReporter()
        assert reporter.template_path is None

    def test_init_with_template_path(self, tmp_path):
        """Test initialization with template path."""
        template_file = tmp_path / "test.md"
        template_file.write_text("# Test")
        reporter = TemplateReporter(template_path=template_file)
        assert reporter.template_path == template_file

    def test_template_path_setter(self, tmp_path):
        """Test setting template path after initialization."""
        reporter = TemplateReporter()
        template_file = tmp_path / "test.md"
        template_file.write_text("# Test")
        reporter.template_path = template_file
        assert reporter.template_path == template_file

    def test_get_template_context(self, sample_report_data):
        """Test that template context contains expected variables."""
        reporter = TemplateReporter()
        context = reporter._get_template_context(sample_report_data)

        # Check metadata
        assert context["root_package"] == "test-package"
        assert context["language"] == "Rust"
        assert context["registry"] == "crates.io"
        assert context["version"] == "1.0.0"
        assert context["timestamp"] == "2024-01-15 10:30:00"
        assert context["max_depth"] == 50

        # Check statistics
        assert context["total_dependencies"] == 10
        assert context["packaged_count"] == 7
        assert context["missing_count"] == 3

        # Check optional stats
        assert context["include_optional"] is True
        assert context["optional_total"] == 2
        assert context["optional_packaged"] == 1
        assert context["optional_missing"] == 1

        # Check package lists are sorted
        assert context["missing_packages"] == [
            "missing1",
            "missing2",
        ]  # missing3 is optional
        assert context["optional_missing_packages"] == ["missing3"]

        # Check flags
        assert context["missing_only"] is False

    def test_get_template_context_excludes_tree(self, sample_report_data):
        """Test that raw tree object is not exposed in context."""
        reporter = TemplateReporter()
        context = reporter._get_template_context(sample_report_data)

        # Tree should NOT be in the context (security/simplicity)
        assert "tree" not in context

    def test_generate_without_jinja2(self, sample_report_data, monkeypatch):
        """Test error when Jinja2 is not available."""
        reporter = TemplateReporter(template_path=Path("test.md"))
        reporter._jinja2_available = False  # Simulate Jinja2 not installed

        with pytest.raises(RuntimeError, match="Jinja2 is required"):
            reporter.generate(sample_report_data)

    def test_generate_without_template_path(self, sample_report_data):
        """Test error when template path is not set."""
        reporter = TemplateReporter()
        reporter._jinja2_available = True

        with pytest.raises(RuntimeError, match="No template path specified"):
            reporter.generate(sample_report_data)

    def test_generate_with_nonexistent_template(self, sample_report_data, tmp_path):
        """Test error when template file doesn't exist."""
        reporter = TemplateReporter(template_path=tmp_path / "nonexistent.md")
        reporter._jinja2_available = True

        with pytest.raises(FileNotFoundError, match="Template file not found"):
            reporter.generate(sample_report_data)

    @pytest.mark.parametrize("has_jinja2", [True])
    def test_generate_basic_template(self, sample_report_data, tmp_path, has_jinja2):
        """Test generating report with basic template."""
        pytest.importorskip("jinja2")

        template_content = """# Report for {{ root_package }}

Generated: {{ timestamp }}
Language: {{ language }}
Registry: {{ registry }}

## Summary
- Total: {{ total_dependencies }}
- Packaged: {{ packaged_count }}
- Missing: {{ missing_count }}
"""
        template_file = tmp_path / "basic.md"
        template_file.write_text(template_content)

        reporter = TemplateReporter(template_path=template_file)
        result = reporter.generate(sample_report_data)

        assert "# Report for test-package" in result
        assert "Generated: 2024-01-15 10:30:00" in result
        assert "Language: Rust" in result
        assert "Registry: crates.io" in result
        assert "- Total: 10" in result
        assert "- Packaged: 7" in result
        assert "- Missing: 3" in result

    @pytest.mark.parametrize("has_jinja2", [True])
    def test_generate_with_loops(self, sample_report_data, tmp_path, has_jinja2):
        """Test generating report with Jinja2 loops."""
        pytest.importorskip("jinja2")

        template_content = """# Missing Packages

{% for pkg in missing_packages %}
- {{ pkg }}
{% endfor %}
"""
        template_file = tmp_path / "loops.md"
        template_file.write_text(template_content)

        reporter = TemplateReporter(template_path=template_file)
        result = reporter.generate(sample_report_data)

        assert "- missing1" in result
        assert "- missing2" in result

    @pytest.mark.parametrize("has_jinja2", [True])
    def test_generate_with_conditionals(self, sample_report_data, tmp_path, has_jinja2):
        """Test generating report with Jinja2 conditionals."""
        pytest.importorskip("jinja2")

        template_content = """{% if include_optional %}
Optional dependencies were included.
{% endif %}

{% if missing_count > 0 %}
There are {{ missing_count }} missing packages.
{% else %}
All packages are available!
{% endif %}
"""
        template_file = tmp_path / "conditionals.md"
        template_file.write_text(template_content)

        reporter = TemplateReporter(template_path=template_file)
        result = reporter.generate(sample_report_data)

        assert "Optional dependencies were included." in result
        assert "There are 3 missing packages." in result
        assert "All packages are available!" not in result

    @pytest.mark.parametrize("has_jinja2", [True])
    def test_generate_with_optional_stats(
        self, sample_report_data, tmp_path, has_jinja2
    ):
        """Test template can access optional dependency statistics."""
        pytest.importorskip("jinja2")

        template_content = """## Optional Dependencies
- Total: {{ optional_total }}
- Packaged: {{ optional_packaged }}
- Missing: {{ optional_missing }}

{% for pkg in optional_missing_packages %}
- {{ pkg }} (optional)
{% endfor %}
"""
        template_file = tmp_path / "optional.md"
        template_file.write_text(template_content)

        reporter = TemplateReporter(template_path=template_file)
        result = reporter.generate(sample_report_data)

        assert "- Total: 2" in result
        assert "- Packaged: 1" in result
        assert "- Missing: 1" in result
        assert "- missing3 (optional)" in result

    @pytest.mark.parametrize("has_jinja2", [True])
    def test_generate_strict_undefined(self, sample_report_data, tmp_path, has_jinja2):
        """Test that undefined variables raise an error."""
        jinja2 = pytest.importorskip("jinja2")

        template_content = """{{ undefined_variable }}"""
        template_file = tmp_path / "undefined.md"
        template_file.write_text(template_content)

        reporter = TemplateReporter(template_path=template_file)

        with pytest.raises(jinja2.UndefinedError):
            reporter.generate(sample_report_data)

    def test_get_output_filename_with_template(self, sample_report_data, tmp_path):
        """Test output filename generation with template path."""
        template_file = tmp_path / "my_custom_template.md"
        template_file.write_text("# Test")

        reporter = TemplateReporter(template_path=template_file)
        filename = reporter.get_output_filename(sample_report_data)

        assert "woolly_test-package_my_custom_template_" in filename
        assert filename.endswith(".md")

    def test_get_output_filename_without_template(self, sample_report_data):
        """Test output filename generation without template path."""
        reporter = TemplateReporter()
        filename = reporter.get_output_filename(sample_report_data)

        assert "woolly_test-package_template_" in filename
        assert filename.endswith(".md")


class TestTemplateReporterIntegration:
    """Integration tests for template reporter with full workflow."""

    @pytest.mark.parametrize("has_jinja2", [True])
    def test_full_report_generation(self, sample_report_data, tmp_path, has_jinja2):
        """Test complete report generation workflow."""
        pytest.importorskip("jinja2")

        template_content = """# Dependency Report: {{ root_package }}

**Generated:** {{ timestamp }}
**Language:** {{ language }}
**Registry:** {{ registry }}
{% if version %}**Version:** {{ version }}{% endif %}

## Summary

| Metric | Value |
|--------|-------|
| Total dependencies | {{ total_dependencies }} |
| Packaged in Fedora | {{ packaged_count }} |
| Missing from Fedora | {{ missing_count }} |
{% if include_optional %}
| Optional total | {{ optional_total }} |
| Optional packaged | {{ optional_packaged }} |
| Optional missing | {{ optional_missing }} |
{% endif %}

{% if missing_packages %}
## Missing Required Packages

{% for pkg in missing_packages %}
- `{{ pkg }}`
{% endfor %}
{% endif %}

{% if optional_missing_packages %}
## Missing Optional Packages

{% for pkg in optional_missing_packages %}
- `{{ pkg }}` *(optional)*
{% endfor %}
{% endif %}
"""
        template_file = tmp_path / "full_report.md"
        template_file.write_text(template_content)

        reporter = TemplateReporter(template_path=template_file)
        result = reporter.generate(sample_report_data)

        # Check all sections are present
        assert "# Dependency Report: test-package" in result
        assert "**Generated:** 2024-01-15 10:30:00" in result
        assert "**Language:** Rust" in result
        assert "**Version:** 1.0.0" in result
        assert "| Total dependencies | 10 |" in result
        assert "| Packaged in Fedora | 7 |" in result
        assert "| Missing from Fedora | 3 |" in result
        assert "| Optional total | 2 |" in result
        assert "## Missing Required Packages" in result
        assert "- `missing1`" in result
        assert "- `missing2`" in result
        assert "## Missing Optional Packages" in result
        assert "- `missing3` *(optional)*" in result

    @pytest.mark.parametrize("has_jinja2", [True])
    def test_write_report_to_file(self, sample_report_data, tmp_path, has_jinja2):
        """Test writing report to file."""
        pytest.importorskip("jinja2")

        template_content = """# {{ root_package }}
Total: {{ total_dependencies }}
"""
        template_file = tmp_path / "simple.md"
        template_file.write_text(template_content)

        reporter = TemplateReporter(template_path=template_file)
        output_path = reporter.write_report(sample_report_data, output_dir=tmp_path)

        assert output_path is not None
        assert output_path.exists()
        content = output_path.read_text()
        assert "# test-package" in content
        assert "Total: 10" in content

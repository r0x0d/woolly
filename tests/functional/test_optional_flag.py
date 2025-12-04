"""
Functional tests for the --optional flag.

These tests run the actual CLI commands to verify
the optional dependencies feature works end-to-end.

Note: Some tests may require network access and may be slow.
"""

import json

import pytest


class TestOptionalFlagHelp:
    """Tests for --optional flag in help output."""

    @pytest.mark.functional
    def test_optional_flag_in_help(self, cli_runner):
        """Good path: --optional flag appears in help."""
        result = cli_runner("check", "--help")

        assert result.returncode == 0
        assert "--optional" in result.stdout or "-o" in result.stdout

    @pytest.mark.functional
    def test_optional_flag_description(self, cli_runner):
        """Good path: --optional flag has description."""
        result = cli_runner("check", "--help")

        assert result.returncode == 0
        assert "optional" in result.stdout.lower()


class TestOptionalFlagExecution:
    """Tests for --optional flag execution."""

    @pytest.mark.functional
    @pytest.mark.slow
    def test_check_without_optional(self, cli_runner, tmp_path, monkeypatch):
        """Good path: check without --optional works normally."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Use a crate known to have optional dependencies
        result = cli_runner(
            "check", "serde", "--lang", "rust", "--no-progress", "--max-depth", "1"
        )

        assert result.returncode == 0
        assert "serde" in result.stdout
        # Without --optional, we should not see "(optional)" markers in tree
        # (unless the package itself is optional, which serde is not)

    @pytest.mark.functional
    @pytest.mark.slow
    def test_check_with_optional_flag(self, cli_runner, tmp_path, monkeypatch):
        """Good path: check with --optional includes optional dependencies."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check",
            "serde",
            "--lang",
            "rust",
            "--no-progress",
            "--optional",
            "--max-depth",
            "1",
        )

        assert result.returncode == 0
        assert "serde" in result.stdout
        # Should show "Including optional dependencies" message
        assert "optional" in result.stdout.lower()

    @pytest.mark.functional
    @pytest.mark.slow
    def test_check_with_optional_short_flag(self, cli_runner, tmp_path, monkeypatch):
        """Good path: check with -o short flag works."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check",
            "serde",
            "--lang",
            "rust",
            "--no-progress",
            "-o",
            "--max-depth",
            "1",
        )

        assert result.returncode == 0
        assert "serde" in result.stdout
        assert "optional" in result.stdout.lower()

    @pytest.mark.functional
    @pytest.mark.slow
    def test_optional_message_displayed(self, cli_runner, tmp_path, monkeypatch):
        """Good path: message about including optional deps is shown."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check", "cfg-if", "--lang", "rust", "--no-progress", "--optional"
        )

        assert result.returncode == 0
        # Should display the "Including optional dependencies" message
        assert "Including optional dependencies" in result.stdout


class TestOptionalFlagJsonReport:
    """Tests for --optional flag with JSON report output."""

    @pytest.mark.functional
    @pytest.mark.slow
    def test_json_report_includes_optional_metadata(
        self, cli_runner, tmp_path, monkeypatch
    ):
        """Good path: JSON report includes optional metadata."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        result = cli_runner(
            "check",
            "cfg-if",
            "--lang",
            "rust",
            "--no-progress",
            "--optional",
            "--report",
            "json",
        )

        assert result.returncode == 0

        # Find and validate the JSON file
        json_files = list(tmp_path.glob("woolly_*.json"))
        assert len(json_files) == 1

        with open(json_files[0]) as f:
            data = json.load(f)

        # Should have include_optional in metadata
        assert "metadata" in data
        assert data["metadata"]["include_optional"] is True

    @pytest.mark.functional
    @pytest.mark.slow
    def test_json_report_includes_optional_stats(
        self, cli_runner, tmp_path, monkeypatch
    ):
        """Good path: JSON report includes optional dependency stats."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        result = cli_runner(
            "check",
            "serde",
            "--lang",
            "rust",
            "--no-progress",
            "--optional",
            "--report",
            "json",
            "--max-depth",
            "1",
        )

        assert result.returncode == 0

        json_files = list(tmp_path.glob("woolly_*.json"))
        assert len(json_files) == 1

        with open(json_files[0]) as f:
            data = json.load(f)

        # Summary should have optional stats
        assert "summary" in data
        assert "optional" in data["summary"]
        assert "total" in data["summary"]["optional"]
        assert "packaged" in data["summary"]["optional"]
        assert "missing" in data["summary"]["optional"]

    @pytest.mark.functional
    @pytest.mark.slow
    def test_json_report_separates_optional_missing(
        self, cli_runner, tmp_path, monkeypatch
    ):
        """Good path: JSON report separates required and optional missing packages."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        result = cli_runner(
            "check",
            "cfg-if",
            "--lang",
            "rust",
            "--no-progress",
            "--optional",
            "--report",
            "json",
        )

        assert result.returncode == 0

        json_files = list(tmp_path.glob("woolly_*.json"))
        assert len(json_files) == 1

        with open(json_files[0]) as f:
            data = json.load(f)

        # Should have both lists
        assert "missing_packages" in data
        assert "missing_optional_packages" in data


class TestOptionalFlagMarkdownReport:
    """Tests for --optional flag with Markdown report output."""

    @pytest.mark.functional
    @pytest.mark.slow
    def test_markdown_report_includes_optional_info(
        self, cli_runner, tmp_path, monkeypatch
    ):
        """Good path: Markdown report includes optional dependency info."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        result = cli_runner(
            "check",
            "serde",
            "--lang",
            "rust",
            "--no-progress",
            "--optional",
            "--report",
            "markdown",
            "--max-depth",
            "1",
        )

        assert result.returncode == 0

        md_files = list(tmp_path.glob("woolly_*.md"))
        assert len(md_files) == 1

        content = md_files[0].read_text()

        # Should mention optional
        assert "optional" in content.lower()


class TestOptionalFlagPython:
    """Tests for --optional flag with Python packages."""

    @pytest.mark.functional
    @pytest.mark.slow
    def test_python_with_optional_flag(self, cli_runner, tmp_path, monkeypatch):
        """Good path: --optional flag works with Python packages."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # requests has optional dependencies (socks)
        result = cli_runner(
            "check",
            "requests",
            "--lang",
            "python",
            "--no-progress",
            "--optional",
            "--max-depth",
            "1",
        )

        assert result.returncode == 0
        assert "requests" in result.stdout
        assert "optional" in result.stdout.lower()

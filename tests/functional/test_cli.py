"""
Functional tests for woolly CLI.

These tests run the actual CLI commands without mocking.
They test the complete integration of all components.

Note: Some tests may require network access and may be slow.
"""

import json
import subprocess
import sys

import pytest


class TestCliHelp:
    """Tests for CLI help output."""

    @pytest.mark.functional
    def test_help_command(self, cli_runner):
        """Good path: help command works."""
        result = cli_runner("--help")

        assert result.returncode == 0
        assert "woolly" in result.stdout.lower()
        assert "check" in result.stdout.lower()

    @pytest.mark.functional
    def test_check_help(self, cli_runner):
        """Good path: check command help works."""
        result = cli_runner("check", "--help")

        assert result.returncode == 0
        assert "package" in result.stdout.lower()
        assert "--lang" in result.stdout
        assert "--missing-only" in result.stdout


class TestListLanguages:
    """Tests for list-languages command."""

    @pytest.mark.functional
    def test_lists_languages(self, cli_runner):
        """Good path: lists available languages."""
        result = cli_runner("list-languages")

        assert result.returncode == 0
        assert "Rust" in result.stdout
        assert "Python" in result.stdout
        assert "crates.io" in result.stdout
        assert "PyPI" in result.stdout

    @pytest.mark.functional
    def test_shows_aliases(self, cli_runner):
        """Good path: shows language aliases."""
        result = cli_runner("list-languages")

        assert result.returncode == 0
        assert "rs" in result.stdout.lower()
        assert "py" in result.stdout.lower()


class TestListFormats:
    """Tests for list-formats command."""

    @pytest.mark.functional
    def test_lists_formats(self, cli_runner):
        """Good path: lists available formats."""
        result = cli_runner("list-formats")

        assert result.returncode == 0
        assert "stdout" in result.stdout
        assert "json" in result.stdout
        assert "markdown" in result.stdout

    @pytest.mark.functional
    def test_shows_descriptions(self, cli_runner):
        """Good path: shows format descriptions."""
        result = cli_runner("list-formats")

        assert result.returncode == 0
        # Should have some descriptions
        assert "console" in result.stdout.lower() or "output" in result.stdout.lower()


class TestClearCache:
    """Tests for clear-cache command."""

    @pytest.mark.functional
    def test_clear_cache_no_cache(self, cli_runner, tmp_path, monkeypatch):
        """Good path: handles case when no cache exists."""
        # Set cache dir to temp location
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner("clear-cache")

        assert result.returncode == 0
        assert "No cache" in result.stdout or "Cleared" in result.stdout

    @pytest.mark.functional
    def test_clear_cache_fedora_only(self, cli_runner, tmp_path, monkeypatch):
        """Good path: fedora-only flag works."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner("clear-cache", "--fedora-only")

        assert result.returncode == 0


class TestCheckCommandValidation:
    """Tests for check command argument validation."""

    @pytest.mark.functional
    def test_unknown_language_fails(self, cli_runner):
        """Bad path: unknown language fails gracefully."""
        result = cli_runner("check", "some-package", "--lang", "unknown-lang")

        assert result.returncode != 0
        assert "Unknown language" in result.stdout or "unknown" in result.stderr.lower()

    @pytest.mark.functional
    def test_unknown_report_format_fails(self, cli_runner):
        """Bad path: unknown report format fails gracefully."""
        result = cli_runner("check", "some-package", "--report", "unknown-format")

        assert result.returncode != 0
        assert "Unknown" in result.stdout or "unknown" in result.stderr.lower()


class TestCheckCommandRust:
    """Tests for check command with Rust packages.

    Note: These tests make real API calls and may be slow.
    """

    @pytest.mark.functional
    @pytest.mark.slow
    def test_check_simple_crate(self, cli_runner, tmp_path, monkeypatch):
        """Good path: checks a simple Rust crate."""
        # Use temp home to avoid polluting real cache
        monkeypatch.setenv("HOME", str(tmp_path))

        # Use a very simple crate with few/no dependencies
        result = cli_runner("check", "cfg-if", "--lang", "rust", "--no-progress")

        assert result.returncode == 0
        assert "cfg-if" in result.stdout
        assert "crates.io" in result.stdout

    @pytest.mark.functional
    @pytest.mark.slow
    def test_check_with_json_output(self, cli_runner, tmp_path, monkeypatch):
        """Good path: generates JSON report."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        result = cli_runner(
            "check", "cfg-if", "--lang", "rust", "--no-progress", "--report", "json"
        )

        assert result.returncode == 0
        assert "Report saved to" in result.stdout

        # Find and validate the JSON file
        json_files = list(tmp_path.glob("woolly_*.json"))
        assert len(json_files) == 1

        with open(json_files[0]) as f:
            data = json.load(f)

        assert "metadata" in data
        assert data["metadata"]["root_package"] == "cfg-if"
        assert data["metadata"]["language"] == "Rust"

    @pytest.mark.functional
    @pytest.mark.slow
    def test_check_with_markdown_output(self, cli_runner, tmp_path, monkeypatch):
        """Good path: generates Markdown report."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        result = cli_runner(
            "check", "cfg-if", "--lang", "rust", "--no-progress", "--report", "markdown"
        )

        assert result.returncode == 0
        assert "Report saved to" in result.stdout

        # Find and validate the Markdown file
        md_files = list(tmp_path.glob("woolly_*.md"))
        assert len(md_files) == 1

        content = md_files[0].read_text()
        assert "# Dependency Report" in content
        assert "cfg-if" in content

    @pytest.mark.functional
    @pytest.mark.slow
    def test_check_nonexistent_crate(self, cli_runner, tmp_path, monkeypatch):
        """Bad path: handles non-existent crate."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check",
            "this-crate-definitely-does-not-exist-12345",
            "--lang",
            "rust",
            "--no-progress",
        )

        assert result.returncode == 0  # Still succeeds but shows "not found"
        assert "not found" in result.stdout


class TestCheckCommandPython:
    """Tests for check command with Python packages.

    Note: These tests make real API calls and may be slow.
    """

    @pytest.mark.functional
    @pytest.mark.slow
    def test_check_simple_package(self, cli_runner, tmp_path, monkeypatch):
        """Good path: checks a simple Python package."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Use a package with minimal dependencies
        result = cli_runner("check", "six", "--lang", "python", "--no-progress")

        assert result.returncode == 0
        assert "six" in result.stdout
        assert "PyPI" in result.stdout

    @pytest.mark.functional
    @pytest.mark.slow
    def test_check_with_alias(self, cli_runner, tmp_path, monkeypatch):
        """Good path: language alias works."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner("check", "six", "--lang", "py", "--no-progress")

        assert result.returncode == 0
        assert "Python" in result.stdout

    @pytest.mark.functional
    @pytest.mark.slow
    def test_check_nonexistent_package(self, cli_runner, tmp_path, monkeypatch):
        """Bad path: handles non-existent package."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check",
            "this-package-definitely-does-not-exist-12345",
            "--lang",
            "python",
            "--no-progress",
        )

        assert result.returncode == 0  # Still succeeds but shows "not found"
        assert "not found" in result.stdout


class TestCheckCommandOptions:
    """Tests for check command options."""

    @pytest.mark.functional
    @pytest.mark.slow
    def test_missing_only_option(self, cli_runner, tmp_path, monkeypatch):
        """Good path: missing-only option is accepted."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check", "cfg-if", "--lang", "rust", "--missing-only", "--no-progress"
        )

        assert result.returncode == 0
        # Should not show the dependency tree when --missing-only is used
        assert "Dependency Tree:" not in result.stdout

    @pytest.mark.functional
    @pytest.mark.slow
    def test_missing_only_short_option(self, cli_runner, tmp_path, monkeypatch):
        """Good path: missing-only short option (-m) is accepted."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner("check", "cfg-if", "--lang", "rust", "-m", "--no-progress")

        assert result.returncode == 0
        # Should not show the dependency tree when -m is used
        assert "Dependency Tree:" not in result.stdout

    @pytest.mark.functional
    @pytest.mark.slow
    def test_max_depth_option(self, cli_runner, tmp_path, monkeypatch):
        """Good path: max-depth option is accepted."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check", "cfg-if", "--lang", "rust", "--max-depth", "5", "--no-progress"
        )

        assert result.returncode == 0

    @pytest.mark.functional
    @pytest.mark.slow
    def test_exclude_option(self, cli_runner, tmp_path, monkeypatch):
        """Good path: exclude option is accepted and displayed."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check",
            "cfg-if",
            "--lang",
            "rust",
            "--exclude",
            "windows*",
            "--no-progress",
        )

        assert result.returncode == 0
        assert "Excluding dependencies matching" in result.stdout
        assert "windows*" in result.stdout

    @pytest.mark.functional
    @pytest.mark.slow
    def test_exclude_multiple_patterns(self, cli_runner, tmp_path, monkeypatch):
        """Good path: multiple exclude patterns are accepted."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check",
            "cfg-if",
            "--lang",
            "rust",
            "--exclude",
            "windows*",
            "--exclude",
            "*-sys",
            "--no-progress",
        )

        assert result.returncode == 0
        assert "Excluding dependencies matching" in result.stdout
        assert "windows*" in result.stdout
        assert "*-sys" in result.stdout

    @pytest.mark.functional
    @pytest.mark.slow
    def test_exclude_short_option(self, cli_runner, tmp_path, monkeypatch):
        """Good path: -e short option works."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check", "cfg-if", "--lang", "rust", "-e", "win*", "--no-progress"
        )

        assert result.returncode == 0
        assert "Excluding dependencies matching" in result.stdout

    @pytest.mark.functional
    @pytest.mark.slow
    def test_debug_option(self, cli_runner, tmp_path, monkeypatch):
        """Good path: debug option creates log file."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check", "cfg-if", "--lang", "rust", "--debug", "--no-progress"
        )

        assert result.returncode == 0
        assert "Log saved to" in result.stdout

        # Check log file was created
        log_dir = tmp_path / ".local" / "state" / "woolly" / "logs"
        if log_dir.exists():
            log_files = list(log_dir.glob("woolly_*.log"))
            assert len(log_files) >= 1

    @pytest.mark.functional
    @pytest.mark.slow
    def test_version_option(self, cli_runner, tmp_path, monkeypatch):
        """Good path: version option is accepted."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = cli_runner(
            "check", "cfg-if", "--lang", "rust", "--version", "1.0.0", "--no-progress"
        )

        assert result.returncode == 0
        # Version should appear in output
        assert "1.0.0" in result.stdout


class TestCliModuleEntry:
    """Tests for CLI module entry point."""

    @pytest.mark.functional
    def test_module_invocation(self):
        """Good path: can invoke as python -m woolly."""
        result = subprocess.run(
            [sys.executable, "-m", "woolly", "--help"], capture_output=True, text=True
        )

        assert result.returncode == 0
        assert "woolly" in result.stdout.lower()

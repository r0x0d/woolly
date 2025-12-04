"""
Unit tests for other woolly commands (clear-cache, list-languages, list-formats).

Tests cover:
- Good path: command execution
- Critical path: correct output
"""

from unittest.mock import MagicMock

import pytest

from woolly.cache import write_cache
from woolly.commands.clear_cache import clear_cache_cmd
from woolly.commands.list_formats import list_formats_cmd
from woolly.commands.list_languages import list_languages_cmd


class TestClearCacheCommand:
    """Tests for clear_cache_cmd function."""

    @pytest.mark.unit
    def test_clears_all_caches(self, temp_cache_dir, mocker):
        """Good path: clears all caches when no flag provided."""
        # Create some cache entries
        write_cache("ns1", "key1", "data1")
        write_cache("ns2", "key2", "data2")

        mock_console = MagicMock()
        mocker.patch("woolly.commands.clear_cache.console", mock_console)

        clear_cache_cmd(fedora_only=False)

        # Should print success message
        mock_console.print.assert_called()
        call_str = str(mock_console.print.call_args_list)
        assert "Cleared" in call_str

    @pytest.mark.unit
    def test_clears_fedora_only(self, temp_cache_dir, mocker):
        """Good path: clears only Fedora cache when flag provided."""
        write_cache("fedora", "key", "data")
        write_cache("crates", "key", "data")

        mock_console = MagicMock()
        mocker.patch("woolly.commands.clear_cache.console", mock_console)

        clear_cache_cmd(fedora_only=True)

        mock_console.print.assert_called()
        call_str = str(mock_console.print.call_args_list)
        assert "Fedora" in call_str

    @pytest.mark.unit
    def test_handles_empty_cache(self, temp_cache_dir, mocker):
        """Good path: handles case when no cache exists."""
        mock_console = MagicMock()
        mocker.patch("woolly.commands.clear_cache.console", mock_console)

        clear_cache_cmd(fedora_only=False)

        mock_console.print.assert_called()
        call_str = str(mock_console.print.call_args_list)
        assert "No cache" in call_str


class TestListLanguagesCommand:
    """Tests for list_languages_cmd function."""

    @pytest.mark.unit
    def test_prints_table(self, mocker):
        """Good path: prints a table of languages."""
        mock_console = MagicMock()
        mocker.patch("woolly.commands.list_languages.console", mock_console)

        list_languages_cmd()

        mock_console.print.assert_called_once()
        # The argument should be a Table
        call_args = mock_console.print.call_args[0][0]
        assert hasattr(call_args, "columns")  # Rich Table has columns


class TestListFormatsCommand:
    """Tests for list_formats_cmd function."""

    @pytest.mark.unit
    def test_prints_table(self, mocker):
        """Good path: prints a table of formats."""
        mock_console = MagicMock()
        mocker.patch("woolly.commands.list_formats.console", mock_console)

        list_formats_cmd()

        mock_console.print.assert_called_once()
        # The argument should be a Table
        call_args = mock_console.print.call_args[0][0]
        assert hasattr(call_args, "columns")  # Rich Table has columns

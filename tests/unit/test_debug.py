"""
Unit tests for woolly.debug module.

Tests cover:
- Good path: logger setup, message logging
- Critical path: debug mode toggle, log file creation
- Bad path: logging without setup
"""

import logging

import pytest

from woolly.debug import (
    get_log_file,
    get_logger,
    is_debug_enabled,
    log,
    log_api_request,
    log_api_response,
    log_cache_hit,
    log_cache_miss,
    log_command_output,
    log_debug,
    log_error,
    log_info,
    log_package_check,
    log_warning,
    setup_logger,
)


class TestSetupLogger:
    """Tests for setup_logger function."""

    @pytest.mark.unit
    def test_creates_log_file(self, temp_log_dir):
        """Good path: creates log file in log directory."""
        setup_logger(debug=False)

        log_file = get_log_file()
        assert log_file is not None
        assert log_file.exists()
        assert log_file.parent == temp_log_dir

    @pytest.mark.unit
    def test_log_file_has_timestamp(self, temp_log_dir):
        """Good path: log file name contains timestamp."""
        setup_logger()
        log_file = get_log_file()
        assert log_file is not None
        assert "woolly_" in log_file.name
        assert log_file.suffix == ".log"

    @pytest.mark.unit
    def test_returns_logger_instance(self, temp_log_dir):
        """Good path: returns a Logger instance."""
        logger = setup_logger()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "woolly"

    @pytest.mark.unit
    def test_debug_mode_sets_flag(self, temp_log_dir):
        """Critical path: debug flag is properly set."""
        setup_logger(debug=True)
        assert is_debug_enabled() is True

    @pytest.mark.unit
    def test_debug_mode_disabled_by_default(self, temp_log_dir):
        """Good path: debug mode is disabled by default."""
        setup_logger(debug=False)
        assert is_debug_enabled() is False

    @pytest.mark.unit
    def test_idempotent_returns_same_logger(self, temp_log_dir):
        """Critical path: multiple calls return same logger."""
        logger1 = setup_logger()
        logger2 = setup_logger()
        assert logger1 is logger2


class TestGetLogger:
    """Tests for get_logger function."""

    @pytest.mark.unit
    def test_creates_logger_if_needed(self, temp_log_dir):
        """Good path: creates logger on first call."""
        logger = get_logger()
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    @pytest.mark.unit
    def test_returns_existing_logger(self, temp_log_dir):
        """Good path: returns existing logger if already created."""
        setup_logger()
        logger = get_logger()
        assert logger.name == "woolly"


class TestLog:
    """Tests for log function."""

    @pytest.mark.unit
    def test_logs_info_by_default(self, temp_log_dir):
        """Good path: logs at INFO level by default."""
        setup_logger()
        log("Test message")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "Test message" in content
        assert "INFO" in content

    @pytest.mark.unit
    def test_logs_with_kwargs(self, temp_log_dir):
        """Good path: includes kwargs in log message."""
        setup_logger()
        log("Action performed", key1="value1", key2="value2")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "key1=value1" in content
        assert "key2=value2" in content

    @pytest.mark.unit
    def test_logs_at_specified_level(self, temp_log_dir):
        """Good path: respects level parameter."""
        setup_logger()

        log("Warning message", level="warning")
        log("Error message", level="error")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "WARNING" in content
        assert "ERROR" in content


class TestLogLevelFunctions:
    """Tests for level-specific log functions."""

    @pytest.mark.unit
    def test_log_info(self, temp_log_dir):
        """Good path: log_info logs at INFO level."""
        setup_logger()
        log_info("Info message")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "INFO" in content
        assert "Info message" in content

    @pytest.mark.unit
    def test_log_warning(self, temp_log_dir):
        """Good path: log_warning logs at WARNING level."""
        setup_logger()
        log_warning("Warning message")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "WARNING" in content

    @pytest.mark.unit
    def test_log_error(self, temp_log_dir):
        """Good path: log_error logs at ERROR level."""
        setup_logger()
        log_error("Error message")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "ERROR" in content

    @pytest.mark.unit
    def test_log_debug_only_in_debug_mode(self, temp_log_dir):
        """Critical path: DEBUG messages only logged in debug mode."""
        setup_logger(debug=False)
        log_debug("Debug message")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "Debug message" not in content

        # Reset and enable debug
        import woolly.debug as debug_module

        debug_module._logger = None
        setup_logger(debug=True)
        log_debug("Debug message 2")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "Debug message 2" in content


class TestLogPackageCheck:
    """Tests for log_package_check function."""

    @pytest.mark.unit
    def test_logs_package_action(self, temp_log_dir):
        """Good path: logs package check with action."""
        setup_logger()
        log_package_check("serde", "Checking version")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "serde" in content
        assert "Checking version" in content

    @pytest.mark.unit
    def test_logs_with_source_and_result(self, temp_log_dir):
        """Good path: includes source and result when provided."""
        setup_logger()
        log_package_check(
            "requests", "Fedora check", source="dnf repoquery", result="packaged"
        )

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "requests" in content
        assert "source=" in content
        assert "result=" in content


class TestLogCommandOutput:
    """Tests for log_command_output function."""

    @pytest.mark.unit
    def test_logs_command_in_debug_mode(self, temp_log_dir):
        """Critical path: command output logged in debug mode."""
        setup_logger(debug=True)
        log_command_output("dnf repoquery --whatprovides", "package|1.0.0", exit_code=0)

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "dnf repoquery" in content
        assert "Exit code: 0" in content

    @pytest.mark.unit
    def test_not_logged_without_debug(self, temp_log_dir):
        """Critical path: command output not logged without debug mode."""
        setup_logger(debug=False)
        log_command_output("dnf repoquery", "output", exit_code=0)

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "dnf repoquery" not in content


class TestLogApiRequest:
    """Tests for log_api_request function."""

    @pytest.mark.unit
    def test_logs_request_in_debug_mode(self, temp_log_dir):
        """Critical path: API request logged in debug mode."""
        setup_logger(debug=True)
        log_api_request("GET", "https://crates.io/api/v1/crates/serde")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "API GET" in content
        assert "crates.io" in content


class TestLogApiResponse:
    """Tests for log_api_response function."""

    @pytest.mark.unit
    def test_logs_response_in_debug_mode(self, temp_log_dir):
        """Critical path: API response logged in debug mode."""
        setup_logger(debug=True)
        log_api_response(200, '{"name": "serde"}')

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "Response: 200" in content


class TestLogCacheHitMiss:
    """Tests for cache logging functions."""

    @pytest.mark.unit
    def test_log_cache_hit(self, temp_log_dir):
        """Good path: cache hit logged in debug mode."""
        setup_logger(debug=True)
        log_cache_hit("crates", "info:serde")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "Cache HIT" in content
        assert "crates/info:serde" in content

    @pytest.mark.unit
    def test_log_cache_miss(self, temp_log_dir):
        """Good path: cache miss logged in debug mode."""
        setup_logger(debug=True)
        log_cache_miss("pypi", "info:requests")

        log_file = get_log_file()
        assert log_file is not None
        content = log_file.read_text()
        assert "Cache MISS" in content
        assert "pypi/info:requests" in content

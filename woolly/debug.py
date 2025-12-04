"""
Logging utilities for woolly.

All operations are logged to ~/.local/state/woolly/logs/
- INFO level: Basic operation info (always logged)
- DEBUG level: Detailed output from commands and API calls (with --debug)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Log directory follows XDG Base Directory specification
LOG_DIR = Path.home() / ".local" / "state" / "woolly" / "logs"

# Global logger instance
_logger: Optional[logging.Logger] = None
_log_file: Optional[Path] = None
_debug_enabled: bool = False


def setup_logger(debug: bool = False) -> logging.Logger:
    """
    Set up the file logger.

    Args:
        debug: If True, log DEBUG level messages (command outputs, API responses).
               If False, only log INFO level messages.

    Returns:
        Configured logger instance.
    """
    global _logger, _log_file, _debug_enabled

    if _logger is not None:
        return _logger

    _debug_enabled = debug
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_file = LOG_DIR / f"woolly_{timestamp}.log"

    _logger = logging.getLogger("woolly")
    _logger.setLevel(logging.DEBUG)  # Logger accepts all, handler filters

    # Clear any existing handlers
    _logger.handlers.clear()

    # File handler - level depends on debug flag
    file_handler = logging.FileHandler(_log_file)
    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    _logger.addHandler(file_handler)

    return _logger


def is_debug_enabled() -> bool:
    """Check if debug logging is enabled."""
    return _debug_enabled


def get_logger() -> logging.Logger:
    """Get the global logger instance, creating it if needed."""
    if _logger is None:
        return setup_logger()
    return _logger


def get_log_file() -> Optional[Path]:
    """Get the path to the current log file."""
    return _log_file


def log(message: str, level: str = "info", **kwargs) -> None:
    """
    Log a message to the file.

    Args:
        message: Message to log.
        level: Log level (debug, info, warning, error).
        **kwargs: Additional context to include.
    """
    logger = get_logger()

    # Format context as key=value pairs
    if kwargs:
        context = " | " + " ".join(f"{k}={v}" for k, v in kwargs.items())
        message = message + context

    log_method = getattr(logger, level, logger.info)
    log_method(message)


def log_debug(message: str, **kwargs) -> None:
    """Log a DEBUG level message (only shown with --debug)."""
    log(message, level="debug", **kwargs)


def log_info(message: str, **kwargs) -> None:
    """Log an INFO level message (always shown)."""
    log(message, level="info", **kwargs)


def log_warning(message: str, **kwargs) -> None:
    """Log a WARNING level message."""
    log(message, level="warning", **kwargs)


def log_error(message: str, **kwargs) -> None:
    """Log an ERROR level message."""
    log(message, level="error", **kwargs)


def log_package_check(
    package: str,
    action: str,
    source: Optional[str] = None,
    result: Optional[str] = None,
) -> None:
    """
    Log a package check operation (INFO level).

    Args:
        package: Package name being checked.
        action: Action being performed.
        source: Source of data (cache, api, repoquery).
        result: Result of the operation.
    """
    log_info(
        f"{action}: {package}",
        package=package,
        source=source,
        result=result,
    )


def log_command_output(command: str, output: str, exit_code: int = 0) -> None:
    """
    Log command execution and output (DEBUG level).

    Args:
        command: The command that was executed.
        output: The command output.
        exit_code: The command exit code.
    """
    log_debug(f"Command: {command}")
    log_debug(f"Exit code: {exit_code}")
    if output:
        for line in output.strip().split("\n"):
            log_debug(f"  > {line}")


def log_api_request(method: str, url: str) -> None:
    """
    Log an API request (DEBUG level).

    Args:
        method: HTTP method (GET, POST, etc.)
        url: The URL being requested.
    """
    log_debug(f"API {method}: {url}")


def log_api_response(status_code: int, body: Optional[str] = None) -> None:
    """
    Log an API response (DEBUG level).

    Args:
        status_code: HTTP status code.
        body: Response body (truncated if too long).
    """
    log_debug(f"Response: {status_code}")
    if body and is_debug_enabled():
        # Truncate very long responses
        if len(body) > 500:
            body = body[:500] + "... (truncated)"
        for line in body.strip().split("\n")[:10]:  # Max 10 lines
            log_debug(f"  > {line}")


def log_cache_hit(namespace: str, key: str) -> None:
    """Log a cache hit (DEBUG level)."""
    log_debug(f"Cache HIT: {namespace}/{key}")


def log_cache_miss(namespace: str, key: str) -> None:
    """Log a cache miss (DEBUG level)."""
    log_debug(f"Cache MISS: {namespace}/{key}")

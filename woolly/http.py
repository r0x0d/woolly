"""
Shared HTTP client configuration for API requests.

This module provides centralized HTTP configuration including
the User-Agent header and common request settings.
"""

import httpx
from importlib.metadata import version

# Version identifier for the User-Agent
VERSION = version("woolly")
PROJECT_URL = "https://github.com/r0x0d/woolly"

# Shared headers for all API requests
DEFAULT_HEADERS = {
    "User-Agent": f"woolly/{VERSION} ({PROJECT_URL})",
}


def get(url: str, **kwargs) -> httpx.Response:
    """
    Make a GET request with default headers.

    Args:
        url: The URL to request.
        **kwargs: Additional arguments passed to httpx.get().

    Returns:
        httpx.Response object.
    """
    headers = kwargs.pop("headers", {})
    merged_headers = {**DEFAULT_HEADERS, **headers}
    return httpx.get(url, headers=merged_headers, **kwargs)

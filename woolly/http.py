"""
Shared HTTP client configuration for API requests.

This module provides centralized HTTP configuration including
the User-Agent header and common request settings.
Uses a lazily-initialized ``httpx.Client`` for connection pooling
and keep-alive across repeated requests to the same host.
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

# Lazily-initialized shared client for connection pooling
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """Return the shared ``httpx.Client``, creating it on first use."""
    global _client
    if _client is None:
        _client = httpx.Client(headers=DEFAULT_HEADERS)
    return _client


def get(url: str, **kwargs) -> httpx.Response:
    """
    Make a GET request with default headers.

    Uses a shared ``httpx.Client`` so that TCP connections are
    reused across requests to the same host.

    Args:
        url: The URL to request.
        **kwargs: Additional arguments passed to ``client.get()``.

    Returns:
        httpx.Response object.
    """
    headers = kwargs.pop("headers", {})
    client = _get_client()
    if headers:
        merged_headers = {**DEFAULT_HEADERS, **headers}
        return client.get(url, headers=merged_headers, **kwargs)
    return client.get(url, **kwargs)

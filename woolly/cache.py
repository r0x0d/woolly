"""
Disk cache helpers for storing API and repoquery results.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path.home() / ".cache" / "woolly"
DEFAULT_CACHE_TTL = 86400 * 7  # 7 days
FEDORA_CACHE_TTL = 86400  # 1 day for Fedora repoquery data


def ensure_cache_dir() -> None:
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_path(namespace: str, key: str) -> Path:
    """Get path for a cache entry."""
    ensure_cache_dir()
    ns_dir = CACHE_DIR / namespace
    ns_dir.mkdir(exist_ok=True)
    safe_key = hashlib.md5(key.encode()).hexdigest()
    return ns_dir / f"{safe_key}.json"


def read_cache(namespace: str, key: str, ttl: int = DEFAULT_CACHE_TTL) -> Optional[Any]:
    """Read from disk cache if not expired."""
    path = get_cache_path(namespace, key)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("timestamp", 0) > ttl:
            return None  # Expired
        return data.get("value")
    except (json.JSONDecodeError, KeyError):
        return None


def write_cache(namespace: str, key: str, value: Any) -> None:
    """Write to disk cache."""
    path = get_cache_path(namespace, key)
    data = {"timestamp": time.time(), "value": value}
    path.write_text(json.dumps(data))


def clear_cache(namespace: Optional[str] = None) -> list[str]:
    """
    Clear disk cache.

    Args:
        namespace: Specific namespace to clear, or None for all.

    Returns:
        List of namespaces that were cleared.
    """
    cleared = []

    if namespace:
        cache_path = CACHE_DIR / namespace
        if cache_path.exists():
            for f in cache_path.glob("*.json"):
                f.unlink()
            cleared.append(namespace)
    else:
        if CACHE_DIR.exists():
            for ns_dir in CACHE_DIR.iterdir():
                if ns_dir.is_dir():
                    for f in ns_dir.glob("*.json"):
                        f.unlink()
                    cleared.append(ns_dir.name)

    return cleared

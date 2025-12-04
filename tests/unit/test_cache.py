"""
Unit tests for woolly.cache module.

Tests cover:
- Good path: normal cache operations (read, write, clear)
- Critical path: cache expiration, namespace isolation
- Bad path: corrupted cache, missing directories
"""

import json
import time

import pytest

from woolly.cache import (
    DEFAULT_CACHE_TTL,
    FEDORA_CACHE_TTL,
    clear_cache,
    ensure_cache_dir,
    get_cache_path,
    read_cache,
    write_cache,
)


class TestEnsureCacheDir:
    """Tests for ensure_cache_dir function."""

    @pytest.mark.unit
    def test_creates_cache_directory(self, temp_cache_dir):
        """Good path: cache directory is created when it doesn't exist."""
        # Remove the directory created by fixture
        import shutil

        shutil.rmtree(temp_cache_dir)

        assert not temp_cache_dir.exists()
        ensure_cache_dir()
        assert temp_cache_dir.exists()

    @pytest.mark.unit
    def test_idempotent_when_exists(self, temp_cache_dir):
        """Good path: no error when directory already exists."""
        ensure_cache_dir()
        ensure_cache_dir()  # Should not raise
        assert temp_cache_dir.exists()


class TestGetCachePath:
    """Tests for get_cache_path function."""

    @pytest.mark.unit
    def test_returns_path_in_namespace(self, temp_cache_dir):
        """Good path: returns correct path structure."""
        path = get_cache_path("test_ns", "test_key")
        assert path.parent.name == "test_ns"
        assert path.suffix == ".json"

    @pytest.mark.unit
    def test_creates_namespace_directory(self, temp_cache_dir):
        """Good path: creates namespace directory if needed."""
        ns_dir = temp_cache_dir / "new_namespace"
        assert not ns_dir.exists()

        get_cache_path("new_namespace", "some_key")
        assert ns_dir.exists()

    @pytest.mark.unit
    def test_consistent_hash_for_same_key(self, temp_cache_dir):
        """Critical path: same key always produces same path."""
        path1 = get_cache_path("ns", "my_key")
        path2 = get_cache_path("ns", "my_key")
        assert path1 == path2

    @pytest.mark.unit
    def test_different_keys_produce_different_paths(self, temp_cache_dir):
        """Critical path: different keys produce different paths."""
        path1 = get_cache_path("ns", "key1")
        path2 = get_cache_path("ns", "key2")
        assert path1 != path2


class TestWriteCache:
    """Tests for write_cache function."""

    @pytest.mark.unit
    def test_writes_json_data(self, temp_cache_dir):
        """Good path: writes data in correct JSON format."""
        write_cache("test", "key", {"foo": "bar"})

        path = get_cache_path("test", "key")
        data = json.loads(path.read_text())

        assert "timestamp" in data
        assert data["value"] == {"foo": "bar"}

    @pytest.mark.unit
    def test_writes_various_types(self, temp_cache_dir):
        """Good path: handles different value types."""
        # String
        write_cache("test", "str_key", "hello")
        assert read_cache("test", "str_key") == "hello"

        # List
        write_cache("test", "list_key", [1, 2, 3])
        assert read_cache("test", "list_key") == [1, 2, 3]

        # None-like value (False is used for "not found" cache)
        write_cache("test", "false_key", False)
        assert read_cache("test", "false_key") is False

    @pytest.mark.unit
    def test_overwrites_existing(self, temp_cache_dir):
        """Good path: overwrites existing cache entry."""
        write_cache("test", "key", "old_value")
        write_cache("test", "key", "new_value")

        assert read_cache("test", "key") == "new_value"


class TestReadCache:
    """Tests for read_cache function."""

    @pytest.mark.unit
    def test_returns_cached_value(self, temp_cache_dir):
        """Good path: returns cached value when valid."""
        write_cache("test", "key", {"data": "value"})
        result = read_cache("test", "key")
        assert result == {"data": "value"}

    @pytest.mark.unit
    def test_returns_none_for_missing(self, temp_cache_dir):
        """Good path: returns None for non-existent key."""
        result = read_cache("test", "nonexistent")
        assert result is None

    @pytest.mark.unit
    def test_returns_none_for_expired(self, temp_cache_dir):
        """Critical path: returns None for expired entries."""
        path = get_cache_path("test", "expired_key")
        expired_data = {
            "timestamp": time.time() - 100000,  # Very old
            "value": "old_data",
        }
        path.write_text(json.dumps(expired_data))

        result = read_cache("test", "expired_key", ttl=3600)
        assert result is None

    @pytest.mark.unit
    def test_respects_custom_ttl(self, temp_cache_dir):
        """Critical path: respects custom TTL parameter."""
        path = get_cache_path("test", "ttl_key")
        # 1 hour old
        old_data = {"timestamp": time.time() - 3600, "value": "data"}
        path.write_text(json.dumps(old_data))

        # Should be expired with 30 min TTL
        assert read_cache("test", "ttl_key", ttl=1800) is None

        # Should be valid with 2 hour TTL
        assert read_cache("test", "ttl_key", ttl=7200) == "data"

    @pytest.mark.unit
    def test_handles_corrupted_json(self, temp_cache_dir):
        """Bad path: returns None for corrupted JSON."""
        path = get_cache_path("test", "corrupted")
        path.write_text("not valid json {{{")

        result = read_cache("test", "corrupted")
        assert result is None

    @pytest.mark.unit
    def test_handles_missing_keys_in_data(self, temp_cache_dir):
        """Bad path: returns None for malformed cache entry."""
        path = get_cache_path("test", "malformed")
        path.write_text(json.dumps({"wrong_key": "data"}))

        result = read_cache("test", "malformed")
        assert result is None


class TestClearCache:
    """Tests for clear_cache function."""

    @pytest.mark.unit
    def test_clears_specific_namespace(self, temp_cache_dir):
        """Good path: clears only specified namespace."""
        write_cache("ns1", "key1", "data1")
        write_cache("ns2", "key2", "data2")

        cleared = clear_cache("ns1")

        assert cleared == ["ns1"]
        assert read_cache("ns1", "key1") is None
        assert read_cache("ns2", "key2") == "data2"

    @pytest.mark.unit
    def test_clears_all_namespaces(self, temp_cache_dir):
        """Good path: clears all namespaces when no namespace specified."""
        write_cache("ns1", "key1", "data1")
        write_cache("ns2", "key2", "data2")
        write_cache("ns3", "key3", "data3")

        cleared = clear_cache()

        assert set(cleared) == {"ns1", "ns2", "ns3"}
        assert read_cache("ns1", "key1") is None
        assert read_cache("ns2", "key2") is None
        assert read_cache("ns3", "key3") is None

    @pytest.mark.unit
    def test_returns_empty_for_nonexistent_namespace(self, temp_cache_dir):
        """Good path: returns empty list for non-existent namespace."""
        cleared = clear_cache("nonexistent")
        assert cleared == []

    @pytest.mark.unit
    def test_returns_empty_when_no_cache(self, temp_cache_dir):
        """Good path: returns empty list when cache is empty."""
        cleared = clear_cache()
        assert cleared == []


class TestCacheConstants:
    """Tests for cache configuration constants."""

    @pytest.mark.unit
    def test_default_ttl_is_7_days(self):
        """Verify default TTL is 7 days in seconds."""
        assert DEFAULT_CACHE_TTL == 86400 * 7

    @pytest.mark.unit
    def test_fedora_ttl_is_1_day(self):
        """Verify Fedora cache TTL is 1 day in seconds."""
        assert FEDORA_CACHE_TTL == 86400

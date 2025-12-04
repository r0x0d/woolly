"""
Unit tests for woolly.languages.rust module.

Tests cover:
- Good path: fetching crate info and dependencies
- Critical path: caching, error handling
- Bad path: 404 responses, API errors
"""

import pytest

from woolly.languages.base import Dependency, PackageInfo
from woolly.languages.rust import RustProvider


class TestRustProviderAttributes:
    """Tests for RustProvider class attributes."""

    @pytest.mark.unit
    def test_provider_attributes(self):
        """Good path: provider has correct attributes."""
        provider = RustProvider()
        assert provider.name == "rust"
        assert provider.display_name == "Rust"
        assert provider.registry_name == "crates.io"
        assert provider.fedora_provides_prefix == "crate"
        assert provider.cache_namespace == "crates"


class TestRustProviderFetchPackageInfo:
    """Tests for RustProvider.fetch_package_info method."""

    @pytest.mark.unit
    def test_returns_package_info(
        self, temp_cache_dir, mocker, make_httpx_response, mock_crates_io_response
    ):
        """Good path: returns PackageInfo for existing crate."""
        provider = RustProvider()

        response = make_httpx_response(200, mock_crates_io_response)
        mocker.patch("httpx.get", return_value=response)

        info = provider.fetch_package_info("serde")

        assert isinstance(info, PackageInfo)
        assert info.name == "serde"
        assert info.latest_version == "1.0.200"
        assert info.description == "A serialization framework for Rust"

    @pytest.mark.unit
    def test_returns_none_for_404(self, temp_cache_dir, mocker, make_httpx_response):
        """Bad path: returns None for non-existent crate."""
        provider = RustProvider()

        response = make_httpx_response(404)
        mocker.patch("httpx.get", return_value=response)

        info = provider.fetch_package_info("nonexistent-crate-12345")

        assert info is None

    @pytest.mark.unit
    def test_raises_on_server_error(self, temp_cache_dir, mocker, make_httpx_response):
        """Bad path: raises RuntimeError on server error."""
        provider = RustProvider()

        response = make_httpx_response(500)
        mocker.patch("httpx.get", return_value=response)

        with pytest.raises(RuntimeError) as exc_info:
            provider.fetch_package_info("some-crate")

        assert "500" in str(exc_info.value)

    @pytest.mark.unit
    def test_uses_cache(
        self, temp_cache_dir, mocker, make_httpx_response, mock_crates_io_response
    ):
        """Critical path: uses cached data on subsequent calls."""
        provider = RustProvider()

        response = make_httpx_response(200, mock_crates_io_response)
        mock_get = mocker.patch("httpx.get", return_value=response)

        # First call
        provider.fetch_package_info("serde")
        # Second call should use cache
        provider.fetch_package_info("serde")

        assert mock_get.call_count == 1

    @pytest.mark.unit
    def test_caches_404_response(self, temp_cache_dir, mocker, make_httpx_response):
        """Critical path: caches 404 responses to avoid repeated API calls."""
        provider = RustProvider()

        response = make_httpx_response(404)
        mock_get = mocker.patch("httpx.get", return_value=response)

        # First call
        result1 = provider.fetch_package_info("nonexistent")
        # Second call should use cache
        result2 = provider.fetch_package_info("nonexistent")

        assert result1 is None
        assert result2 is None
        assert mock_get.call_count == 1


class TestRustProviderFetchDependencies:
    """Tests for RustProvider.fetch_dependencies method."""

    @pytest.mark.unit
    def test_returns_dependencies(
        self, temp_cache_dir, mocker, make_httpx_response, mock_crates_io_deps_response
    ):
        """Good path: returns list of dependencies."""
        provider = RustProvider()

        response = make_httpx_response(200, mock_crates_io_deps_response)
        mocker.patch("httpx.get", return_value=response)

        deps = provider.fetch_dependencies("serde", "1.0.200")

        assert len(deps) == 2
        assert all(isinstance(d, Dependency) for d in deps)
        assert deps[0].name == "serde_derive"
        assert deps[0].optional is True

    @pytest.mark.unit
    def test_returns_empty_on_error(self, temp_cache_dir, mocker, make_httpx_response):
        """Bad path: returns empty list on API error."""
        provider = RustProvider()

        response = make_httpx_response(404)
        mocker.patch("httpx.get", return_value=response)

        deps = provider.fetch_dependencies("nonexistent", "1.0.0")

        assert deps == []

    @pytest.mark.unit
    def test_handles_missing_optional_fields(
        self, temp_cache_dir, mocker, make_httpx_response
    ):
        """Good path: handles dependencies without optional fields."""
        provider = RustProvider()

        response_data = {
            "dependencies": [
                {"crate_id": "minimal-dep", "req": "^1.0"},  # No optional or kind
            ]
        }
        response = make_httpx_response(200, response_data)
        mocker.patch("httpx.get", return_value=response)

        deps = provider.fetch_dependencies("test", "1.0.0")

        assert len(deps) == 1
        assert deps[0].optional is False
        assert deps[0].kind == "normal"

    @pytest.mark.unit
    def test_uses_cache(
        self, temp_cache_dir, mocker, make_httpx_response, mock_crates_io_deps_response
    ):
        """Critical path: uses cached dependencies."""
        provider = RustProvider()

        response = make_httpx_response(200, mock_crates_io_deps_response)
        mock_get = mocker.patch("httpx.get", return_value=response)

        provider.fetch_dependencies("serde", "1.0.200")
        provider.fetch_dependencies("serde", "1.0.200")

        assert mock_get.call_count == 1


class TestRustProviderAlternativeNames:
    """Tests for RustProvider.get_alternative_names method."""

    @pytest.mark.unit
    def test_hyphen_to_underscore(self):
        """Critical path: suggests underscore variant for hyphenated names."""
        provider = RustProvider()

        alternatives = provider.get_alternative_names("my-crate")

        assert "my_crate" in alternatives

    @pytest.mark.unit
    def test_underscore_to_hyphen(self):
        """Critical path: suggests hyphenated variant for underscored names."""
        provider = RustProvider()

        alternatives = provider.get_alternative_names("my_crate")

        assert "my-crate" in alternatives

    @pytest.mark.unit
    def test_no_alternatives_for_simple_names(self):
        """Good path: no alternatives for names without hyphens or underscores."""
        provider = RustProvider()

        alternatives = provider.get_alternative_names("serde")

        assert alternatives == []

    @pytest.mark.unit
    def test_mixed_name(self):
        """Good path: handles names with both hyphens and underscores."""
        provider = RustProvider()

        # Name with hyphen
        alt1 = provider.get_alternative_names("my-crate-name")
        assert "my_crate_name" in alt1

        # Name with underscore
        alt2 = provider.get_alternative_names("my_crate_name")
        assert "my-crate-name" in alt2

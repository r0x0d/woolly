"""
Unit tests for woolly.languages registry module.

Tests cover:
- Good path: provider lookup, listing
- Critical path: alias resolution
- Bad path: unknown providers
"""

import pytest

from woolly.languages import (
    ALIASES,
    PROVIDERS,
    get_available_languages,
    get_provider,
    list_providers,
)
from woolly.languages.base import LanguageProvider
from woolly.languages.python import PythonProvider
from woolly.languages.rust import RustProvider


class TestProviderRegistry:
    """Tests for provider registry constants."""

    @pytest.mark.unit
    def test_rust_registered(self):
        """Good path: Rust provider is registered."""
        assert "rust" in PROVIDERS
        assert PROVIDERS["rust"] == RustProvider

    @pytest.mark.unit
    def test_python_registered(self):
        """Good path: Python provider is registered."""
        assert "python" in PROVIDERS
        assert PROVIDERS["python"] == PythonProvider

    @pytest.mark.unit
    def test_aliases_defined(self):
        """Good path: aliases are defined."""
        assert "rs" in ALIASES
        assert "py" in ALIASES
        assert ALIASES["rs"] == "rust"
        assert ALIASES["py"] == "python"


class TestGetProvider:
    """Tests for get_provider function."""

    @pytest.mark.unit
    def test_get_rust_provider(self):
        """Good path: returns Rust provider."""
        provider = get_provider("rust")

        assert isinstance(provider, RustProvider)
        assert isinstance(provider, LanguageProvider)

    @pytest.mark.unit
    def test_get_python_provider(self):
        """Good path: returns Python provider."""
        provider = get_provider("python")

        assert isinstance(provider, PythonProvider)

    @pytest.mark.unit
    def test_alias_resolution(self):
        """Critical path: resolves aliases correctly."""
        # Rust aliases
        assert isinstance(get_provider("rs"), RustProvider)
        assert isinstance(get_provider("crate"), RustProvider)
        assert isinstance(get_provider("crates"), RustProvider)

        # Python aliases
        assert isinstance(get_provider("py"), PythonProvider)
        assert isinstance(get_provider("pypi"), PythonProvider)

    @pytest.mark.unit
    def test_case_insensitive(self):
        """Good path: language lookup is case-insensitive."""
        assert isinstance(get_provider("RUST"), RustProvider)
        assert isinstance(get_provider("Rust"), RustProvider)
        assert isinstance(get_provider("PYTHON"), PythonProvider)

    @pytest.mark.unit
    def test_returns_none_for_unknown(self):
        """Bad path: returns None for unknown language."""
        provider = get_provider("unknown-language")

        assert provider is None

    @pytest.mark.unit
    def test_returns_new_instance(self):
        """Good path: returns new instance each call."""
        provider1 = get_provider("rust")
        provider2 = get_provider("rust")

        assert provider1 is not provider2


class TestListProviders:
    """Tests for list_providers function."""

    @pytest.mark.unit
    def test_returns_list_of_tuples(self):
        """Good path: returns list of tuples."""
        providers = list_providers()

        assert isinstance(providers, list)
        assert len(providers) >= 2  # At least rust and python

        for item in providers:
            assert isinstance(item, tuple)
            assert len(item) == 3  # (id, display_name, aliases)

    @pytest.mark.unit
    def test_includes_rust(self):
        """Good path: includes Rust provider."""
        providers = list_providers()

        rust_entry = next((p for p in providers if p[0] == "rust"), None)
        assert rust_entry is not None
        assert rust_entry[1] == "Rust"
        assert "rs" in rust_entry[2]

    @pytest.mark.unit
    def test_includes_python(self):
        """Good path: includes Python provider."""
        providers = list_providers()

        python_entry = next((p for p in providers if p[0] == "python"), None)
        assert python_entry is not None
        assert python_entry[1] == "Python"
        assert "py" in python_entry[2]


class TestGetAvailableLanguages:
    """Tests for get_available_languages function."""

    @pytest.mark.unit
    def test_returns_list(self):
        """Good path: returns list of strings."""
        languages = get_available_languages()

        assert isinstance(languages, list)
        assert all(isinstance(lang, str) for lang in languages)

    @pytest.mark.unit
    def test_includes_all_providers(self):
        """Good path: includes all registered providers."""
        languages = get_available_languages()

        assert "rust" in languages
        assert "python" in languages

    @pytest.mark.unit
    def test_does_not_include_aliases(self):
        """Good path: does not include aliases."""
        languages = get_available_languages()

        assert "rs" not in languages
        assert "py" not in languages

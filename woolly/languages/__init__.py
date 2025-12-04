"""
Language providers registry.

This module provides automatic discovery and registration of language providers.
To add a new language, create a module in this directory that defines a class
inheriting from LanguageProvider and add it to PROVIDERS dict.
"""

from typing import Optional

from pydantic import BaseModel, Field

from woolly.languages.base import LanguageProvider
from woolly.languages.python import PythonProvider
from woolly.languages.rust import RustProvider


class ProviderInfo(BaseModel):
    """Information about an available language provider."""

    language_id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)


# Registry of available language providers
# Key: language identifier (used in CLI)
# Value: Provider class
PROVIDERS: dict[str, type[LanguageProvider]] = {
    "rust": RustProvider,
    "python": PythonProvider,
}

# Aliases for convenience
ALIASES: dict[str, str] = {
    "rs": "rust",
    "crate": "rust",
    "crates": "rust",
    "py": "python",
    "pypi": "python",
}


def get_provider(language: str) -> Optional[LanguageProvider]:
    """
    Get an instantiated provider for the specified language.

    Args:
        language: Language identifier or alias (e.g., "rust", "python", "rs", "py")

    Returns:
        Instantiated LanguageProvider, or None if not found.
    """
    # Resolve aliases
    language = language.lower()
    if language in ALIASES:
        language = ALIASES[language]

    provider_class = PROVIDERS.get(language)
    if provider_class is None:
        return None

    return provider_class()


def list_providers() -> list[ProviderInfo]:
    """
    List all available providers.

    Returns:
        List of ProviderInfo objects with language details.
    """
    result = []
    for lang_id, provider_class in PROVIDERS.items():
        # Find aliases for this language
        aliases = [alias for alias, target in ALIASES.items() if target == lang_id]
        result.append(
            ProviderInfo(
                language_id=lang_id,
                display_name=provider_class.display_name,
                aliases=aliases,
            )
        )
    return result


def get_available_languages() -> list[str]:
    """Get list of available language identifiers."""
    return list(PROVIDERS.keys())


__all__ = [
    "LanguageProvider",
    "ProviderInfo",
    "PythonProvider",
    "RustProvider",
    "get_provider",
    "list_providers",
    "get_available_languages",
    "PROVIDERS",
    "ALIASES",
]

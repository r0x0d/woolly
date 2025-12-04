"""
Rust/crates.io language provider.

This provider fetches package information from crates.io and checks
Fedora repositories for Rust crate packages.
"""

from typing import Optional

from woolly import http
from woolly.cache import DEFAULT_CACHE_TTL, read_cache, write_cache
from woolly.debug import (
    log_api_request,
    log_api_response,
    log_cache_hit,
    log_cache_miss,
)
from woolly.languages.base import Dependency, LanguageProvider, PackageInfo

CRATES_API = "https://crates.io/api/v1/crates"


class RustProvider(LanguageProvider):
    """Provider for Rust crates via crates.io."""

    name = "rust"
    display_name = "Rust"
    registry_name = "crates.io"
    fedora_provides_prefix = "crate"
    cache_namespace = "crates"

    def fetch_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """Fetch crate information from crates.io."""
        cache_key = f"info:{package_name}"
        cached = read_cache(self.cache_namespace, cache_key, DEFAULT_CACHE_TTL)
        if cached is not None:
            log_cache_hit(self.cache_namespace, cache_key)
            if cached is False:  # Explicit "not found" cache
                return None
            return PackageInfo(
                name=cached["crate"]["name"],
                latest_version=cached["crate"]["newest_version"],
                description=cached["crate"].get("description"),
                homepage=cached["crate"].get("homepage"),
                repository=cached["crate"].get("repository"),
            )

        log_cache_miss(self.cache_namespace, cache_key)
        url = f"{CRATES_API}/{package_name}"
        log_api_request("GET", url)
        r = http.get(url)
        log_api_response(r.status_code, r.text[:500] if r.text else None)

        if r.status_code == 404:
            write_cache(self.cache_namespace, cache_key, False)
            return None
        if r.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch metadata for crate {package_name}: {r.status_code}"
            )

        data = r.json()
        write_cache(self.cache_namespace, cache_key, data)

        return PackageInfo(
            name=data["crate"]["name"],
            latest_version=data["crate"]["newest_version"],
            description=data["crate"].get("description"),
            homepage=data["crate"].get("homepage"),
            repository=data["crate"].get("repository"),
        )

    def fetch_dependencies(self, package_name: str, version: str) -> list[Dependency]:
        """Fetch dependencies for a specific crate version."""
        cache_key = f"deps:{package_name}:{version}"
        cached = read_cache(self.cache_namespace, cache_key, DEFAULT_CACHE_TTL)
        if cached is not None:
            log_cache_hit(self.cache_namespace, cache_key)
            return [
                Dependency(
                    name=d["crate_id"],
                    version_requirement=d["req"],
                    optional=d.get("optional", False),
                    kind=d.get("kind", "normal"),
                )
                for d in cached
            ]

        log_cache_miss(self.cache_namespace, cache_key)
        url = f"{CRATES_API}/{package_name}/{version}/dependencies"
        log_api_request("GET", url)
        r = http.get(url)
        log_api_response(r.status_code, r.text[:500] if r.text else None)

        if r.status_code != 200:
            write_cache(self.cache_namespace, cache_key, [])
            return []

        data = r.json()
        deps = data.get("dependencies", [])
        write_cache(self.cache_namespace, cache_key, deps)

        return [
            Dependency(
                name=d["crate_id"],
                version_requirement=d["req"],
                optional=d.get("optional", False),
                kind=d.get("kind", "normal"),
            )
            for d in deps
        ]

    def get_alternative_names(self, package_name: str) -> list[str]:
        """
        Get alternative names to try for crate lookup.

        Rust crates can use either hyphens or underscores in names,
        but they're treated as equivalent by Cargo.
        """
        alternatives = []

        alt_underscore = package_name.replace("-", "_")
        if alt_underscore != package_name:
            alternatives.append(alt_underscore)

        alt_hyphen = package_name.replace("_", "-")
        if alt_hyphen != package_name:
            alternatives.append(alt_hyphen)

        return alternatives

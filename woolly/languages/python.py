"""
Python/PyPI language provider.

This provider fetches package information from PyPI and checks
Fedora repositories for Python packages.
"""

import re
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

PYPI_API = "https://pypi.org/pypi"


class PythonProvider(LanguageProvider):
    """Provider for Python packages via PyPI."""

    name = "python"
    display_name = "Python"
    registry_name = "PyPI"
    fedora_provides_prefix = "python3dist"
    cache_namespace = "pypi"

    def fetch_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """Fetch package information from PyPI."""
        cache_key = f"info:{package_name}"
        cached = read_cache(self.cache_namespace, cache_key, DEFAULT_CACHE_TTL)
        if cached is not None:
            log_cache_hit(self.cache_namespace, cache_key)
            if cached is False:  # Explicit "not found" cache
                return None
            return PackageInfo(
                name=cached["info"]["name"],
                latest_version=cached["info"]["version"],
                description=cached["info"].get("summary"),
                homepage=cached["info"].get("home_page"),
                repository=cached["info"].get("project_url"),
            )

        log_cache_miss(self.cache_namespace, cache_key)
        url = f"{PYPI_API}/{package_name}/json"
        log_api_request("GET", url)
        r = http.get(url)
        log_api_response(r.status_code, r.text[:500] if r.text else None)

        if r.status_code == 404:
            write_cache(self.cache_namespace, cache_key, False)
            return None
        if r.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch metadata for package {package_name}: {r.status_code}"
            )

        data = r.json()
        write_cache(self.cache_namespace, cache_key, data)

        return PackageInfo(
            name=data["info"]["name"],
            latest_version=data["info"]["version"],
            description=data["info"].get("summary"),
            homepage=data["info"].get("home_page"),
            repository=data["info"].get("project_url"),
        )

    def fetch_dependencies(self, package_name: str, version: str) -> list[Dependency]:
        """
        Fetch dependencies for a specific package version.

        PyPI provides dependencies in the `requires_dist` field.
        """
        cache_key = f"deps:{package_name}:{version}"
        cached = read_cache(self.cache_namespace, cache_key, DEFAULT_CACHE_TTL)
        if cached is not None:
            log_cache_hit(self.cache_namespace, cache_key)
            return [
                Dependency(
                    name=d["name"],
                    version_requirement=d["version_requirement"],
                    optional=d.get("optional", False),
                    kind=d.get("kind", "normal"),
                )
                for d in cached
            ]

        log_cache_miss(self.cache_namespace, cache_key)
        url = f"{PYPI_API}/{package_name}/{version}/json"
        log_api_request("GET", url)
        r = http.get(url)
        log_api_response(r.status_code, r.text[:500] if r.text else None)

        if r.status_code != 200:
            write_cache(self.cache_namespace, cache_key, [])
            return []

        data = r.json()
        requires_dist = data["info"].get("requires_dist") or []

        deps = []
        for req in requires_dist:
            parsed = self._parse_requirement(req)
            if parsed:
                deps.append(parsed)

        # Cache as dicts
        cache_data = [
            {
                "name": d.name,
                "version_requirement": d.version_requirement,
                "optional": d.optional,
                "kind": d.kind,
            }
            for d in deps
        ]
        write_cache(self.cache_namespace, cache_key, cache_data)

        return deps

    def _parse_requirement(self, req_string: str) -> Optional[Dependency]:
        """
        Parse a PEP 508 requirement string.

        Examples:
            "requests>=2.20.0"
            "typing-extensions; python_version < '3.8'"
            "pytest; extra == 'testing'"
        """
        # Check if this is an optional/extra dependency
        is_optional = False
        kind = "normal"

        if "extra ==" in req_string or "extra==" in req_string:
            is_optional = True
            # Keep kind as "normal" so optional dependencies can be included
            # when --optional flag is used

        # Extract the package name and version requirement
        # Handle environment markers (everything after ';')
        if ";" in req_string:
            req_string = req_string.split(";")[0].strip()

        # Match package name and optional version specifier
        # Package names can contain letters, numbers, hyphens, underscores, and dots
        match = re.match(r"^([A-Za-z0-9][-A-Za-z0-9._]*)\s*(.*)$", req_string.strip())

        if not match:
            return None

        name = match.group(1)
        version_req = match.group(2).strip()

        # Handle extras in package name (e.g., "package[extra1,extra2]")
        if "[" in name:
            name = name.split("[")[0]

        return Dependency(
            name=self.normalize_package_name(name),
            version_requirement=version_req or "*",
            optional=is_optional,
            kind=kind,
        )

    def normalize_package_name(self, package_name: str) -> str:
        """
        Normalize a Python package name according to PEP 503.

        Package names are case-insensitive and treat hyphens,
        underscores, and dots as equivalent.
        """
        return re.sub(r"[-_.]+", "-", package_name).lower()

    def get_alternative_names(self, package_name: str) -> list[str]:
        """
        Get alternative names to try for package lookup.

        Python package names can use hyphens, underscores, or dots
        interchangeably.
        """
        alternatives = []
        normalized = self.normalize_package_name(package_name)

        # Try with underscores instead of hyphens
        alt_underscore = normalized.replace("-", "_")
        if alt_underscore != normalized:
            alternatives.append(alt_underscore)

        # Try with dots instead of hyphens
        alt_dot = normalized.replace("-", ".")
        if alt_dot != normalized:
            alternatives.append(alt_dot)

        return alternatives

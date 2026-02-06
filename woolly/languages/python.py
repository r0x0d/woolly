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
from woolly.languages.base import Dependency, FeatureInfo, LanguageProvider, PackageInfo

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
                license=self._extract_license(cached["info"]),
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
            license=self._extract_license(data["info"]),
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
                    group=d.get("group"),
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
                "group": d.group,
            }
            for d in deps
        ]
        write_cache(self.cache_namespace, cache_key, cache_data)

        return deps

    def fetch_features(self, package_name: str, version: str) -> list[FeatureInfo]:
        """
        Fetch extras (groups) for a specific Python package version.

        PyPI provides extras via `provides_extra` and links dependencies
        to extras via `requires_dist` markers.
        """
        cache_key = f"features:{package_name}:{version}"
        cached = read_cache(self.cache_namespace, cache_key, DEFAULT_CACHE_TTL)
        if cached is not None:
            log_cache_hit(self.cache_namespace, cache_key)
            return [
                FeatureInfo(name=f["name"], dependencies=f["dependencies"])
                for f in cached
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
        provides_extra = data["info"].get("provides_extra") or []
        requires_dist = data["info"].get("requires_dist") or []

        # Build a mapping of extra -> dependencies
        extras_map: dict[str, list[str]] = {extra: [] for extra in provides_extra}

        for req in requires_dist:
            extra_name = self._extract_extra_name(req)
            if extra_name and extra_name in extras_map:
                # Extract just the package name from the requirement
                parsed = self._parse_requirement(req)
                if parsed:
                    extras_map[extra_name].append(parsed.name)

        features = [
            FeatureInfo(name=name, dependencies=sorted(deps))
            for name, deps in sorted(extras_map.items())
        ]

        # Cache as dicts
        cache_data = [
            {"name": f.name, "dependencies": f.dependencies} for f in features
        ]
        write_cache(self.cache_namespace, cache_key, cache_data)

        return features

    def _extract_extra_name(self, req_string: str) -> Optional[str]:
        """
        Extract the extra name from a PEP 508 requirement string.

        Examples:
            "PySocks>=1.5.6; extra == 'socks'" -> "socks"
            "requests>=2.20.0" -> None
        """
        match = re.search(r"""extra\s*==\s*['"]([\w-]+)['"]""", req_string)
        if match:
            return match.group(1)
        return None

    # Well-known classifier suffix -> short SPDX-like name
    _CLASSIFIER_LICENSE_MAP: dict[str, str] = {
        "MIT License": "MIT",
        "BSD License": "BSD",
        "ISC License (ISCL)": "ISC",
        "Apache Software License": "Apache-2.0",
        "GNU General Public License v2 (GPLv2)": "GPL-2.0",
        "GNU General Public License v2 or later (GPLv2+)": "GPL-2.0-or-later",
        "GNU General Public License v3 (GPLv3)": "GPL-3.0",
        "GNU General Public License v3 or later (GPLv3+)": "GPL-3.0-or-later",
        "GNU Lesser General Public License v2 (LGPLv2)": "LGPL-2.0",
        "GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.0-or-later",
        "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0",
        "GNU Lesser General Public License v3 or later (LGPLv3+)": "LGPL-3.0-or-later",
        "GNU Affero General Public License v3": "AGPL-3.0",
        "GNU Affero General Public License v3 or later (AGPLv3+)": "AGPL-3.0-or-later",
        "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
        "Eclipse Public License 1.0 (EPL-1.0)": "EPL-1.0",
        "Eclipse Public License 2.0 (EPL-2.0)": "EPL-2.0",
        "The Unlicense (Unlicense)": "Unlicense",
        "Public Domain": "Public Domain",
        "Python Software Foundation License": "PSF",
        "Zope Public License": "ZPL",
        "Academic Free License (AFL)": "AFL",
        "Artistic License": "Artistic",
        "Boost Software License 1.0 (BSL-1.0)": "BSL-1.0",
        "European Union Public Licence 1.1 (EUPL 1.1)": "EUPL-1.1",
        "European Union Public Licence 1.2 (EUPL 1.2)": "EUPL-1.2",
    }

    @staticmethod
    def _looks_like_license_name(value: str) -> bool:
        """
        Heuristic check: does this look like a short license name/identifier
        rather than the full license text?

        A short license name is typically under 100 characters, fits on a
        single line, and does not contain common full-text markers like
        "Permission is hereby granted" or "THE SOFTWARE IS PROVIDED".
        """
        if len(value) > 100:
            return False
        if "\n" in value:
            return False
        # Common full-text markers
        full_text_markers = [
            "permission is hereby granted",
            "the software is provided",
            "redistribution and use",
            "licensed under the",
            "this software",
            "copyright (c)",
            "all rights reserved",
            'provided "as is"',
            "provided 'as is'",
        ]
        lower = value.lower()
        return not any(marker in lower for marker in full_text_markers)

    def _license_from_classifiers(self, info: dict) -> Optional[str]:
        """
        Try to derive a short license name from the trove classifiers.

        PyPI classifiers follow the pattern::

            License :: OSI Approved :: MIT License

        Returns the first match mapped to a short identifier, or the
        classifier suffix as-is if no mapping exists.
        """
        classifiers = info.get("classifiers") or []
        for clf in classifiers:
            if clf.startswith("License :: OSI Approved :: "):
                suffix = clf.split(" :: ")[-1]
                return self._CLASSIFIER_LICENSE_MAP.get(suffix, suffix)
            if clf.startswith("License :: "):
                suffix = clf.split(" :: ")[-1]
                return self._CLASSIFIER_LICENSE_MAP.get(suffix, suffix)
        return None

    def _extract_license(self, info: dict) -> Optional[str]:
        """
        Extract a *short* license identifier from PyPI package info.

        Resolution order:

        1. ``license_expression`` (PEP 639) – always a proper SPDX expression.
        2. ``license`` field, **only** when it looks like a short name
           (not the full license text that older packages sometimes embed).
        3. Trove classifiers (``License :: …``).

        Args:
            info: The ``info`` dict from the PyPI API response.

        Returns:
            Short license string, or None if unavailable.
        """
        # 1. PEP 639 license expression – best source
        license_expr = info.get("license_expression")
        if license_expr and license_expr.strip():
            return license_expr.strip()

        # 2. license field, only if it looks like a short identifier
        license_val = info.get("license")
        if license_val and license_val.strip():
            cleaned = license_val.strip()
            if self._looks_like_license_name(cleaned):
                return cleaned

        # 3. Fall back to classifiers
        return self._license_from_classifiers(info)

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
        group = None

        if "extra ==" in req_string or "extra==" in req_string:
            is_optional = True
            # Keep kind as "normal" so optional dependencies can be included
            # when --optional flag is used
            group = self._extract_extra_name(req_string)

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
            group=group,
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

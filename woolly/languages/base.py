"""
Base abstract class defining the contract for language package providers.

To add support for a new language, create a new module in the `languages/` directory
that implements a class inheriting from `LanguageProvider`. The class must implement
all abstract methods defined here.

Example:
    class GoProvider(LanguageProvider):
        name = "go"
        display_name = "Go"
        registry_name = "Go Modules"
        fedora_provides_prefix = "golang"
        cache_namespace = "go"

        def fetch_package_info(self, package_name: str) -> Optional[PackageInfo]:
            # Fetch from proxy.golang.org or pkg.go.dev
            ...

        def fetch_dependencies(self, package_name: str, version: str) -> list[Dependency]:
            # Fetch dependencies from go.mod
            ...
"""

import re
import subprocess
from abc import ABC, abstractmethod
from typing import Literal, Optional

from pydantic import BaseModel, Field

from woolly.cache import FEDORA_CACHE_TTL, read_cache, write_cache
from woolly.debug import log_cache_hit, log_cache_miss, log_command_output


class PackageInfo(BaseModel):
    """Information about a package from an upstream registry."""

    name: str
    latest_version: str
    description: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None


class Dependency(BaseModel):
    """A package dependency."""

    name: str
    version_requirement: str
    optional: bool = False
    kind: Literal["normal", "dev", "build"] = "normal"


class FedoraPackageStatus(BaseModel):
    """Status of a package in Fedora repositories."""

    is_packaged: bool
    versions: list[str] = Field(default_factory=list)
    package_names: list[str] = Field(default_factory=list)


class LanguageProvider(ABC):
    """
    Abstract base class for language package providers.

    Each language (Rust, Python, Go, etc.) must implement this interface
    to enable checking its packages against Fedora repositories.

    Attributes:
        name: Short identifier for the language (e.g., "rust", "python")
        display_name: Human-readable name (e.g., "Rust", "Python")
        registry_name: Name of the package registry (e.g., "crates.io", "PyPI")
        fedora_provides_prefix: Prefix used in Fedora provides (e.g., "crate", "python3dist")
        cache_namespace: Namespace for caching upstream registry data
    """

    # Class attributes that must be defined by subclasses
    name: str
    display_name: str
    registry_name: str
    fedora_provides_prefix: str
    cache_namespace: str

    # ----------------------------------------------------------------
    # Abstract methods - MUST be implemented by subclasses
    # ----------------------------------------------------------------

    @abstractmethod
    def fetch_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """
        Fetch package information from the upstream registry.

        Args:
            package_name: The name of the package to look up.

        Returns:
            PackageInfo if the package exists, None otherwise.
        """
        pass

    @abstractmethod
    def fetch_dependencies(self, package_name: str, version: str) -> list[Dependency]:
        """
        Fetch dependencies for a specific package version.

        Args:
            package_name: The name of the package.
            version: The specific version to get dependencies for.

        Returns:
            List of Dependency objects.
        """
        pass

    # ----------------------------------------------------------------
    # Concrete methods - shared implementation for all providers
    # ----------------------------------------------------------------

    def get_latest_version(self, package_name: str) -> Optional[str]:
        """
        Get the latest version of a package.

        Args:
            package_name: The name of the package.

        Returns:
            Version string if package exists, None otherwise.
        """
        info = self.fetch_package_info(package_name)
        if info is None:
            return None
        return info.latest_version

    def get_normal_dependencies(
        self,
        package_name: str,
        version: Optional[str] = None,
        include_optional: bool = False,
    ) -> list[tuple[str, str, bool]]:
        """
        Get runtime dependencies for a package.

        This method filters dependencies to only include normal (runtime)
        dependencies. By default, optional dependencies are excluded.

        Args:
            package_name: The name of the package.
            version: Specific version, or None for latest.
            include_optional: If True, include optional dependencies.

        Returns:
            List of tuples: (dependency_name, version_requirement, is_optional)
        """
        if version is None:
            version = self.get_latest_version(package_name)
            if version is None:
                return []

        deps = self.fetch_dependencies(package_name, version)
        return [
            (d.name, d.version_requirement, d.optional)
            for d in deps
            if d.kind == "normal" and (include_optional or not d.optional)
        ]

    def get_fedora_provides_pattern(self, package_name: str) -> str:
        """
        Get the Fedora provides pattern for this package.

        Uses the `fedora_provides_prefix` attribute to construct the pattern.
        Override if your language needs special handling.

        Args:
            package_name: The name of the package.

        Returns:
            Provides pattern string (e.g., "crate(serde)" or "python3dist(requests)")
        """
        normalized = self.normalize_package_name(package_name)
        return f"{self.fedora_provides_prefix}({normalized})"

    def normalize_package_name(self, package_name: str) -> str:
        """
        Normalize a package name to its canonical form.

        Override this method if the language has specific naming conventions
        that differ between the upstream registry and Fedora.

        Args:
            package_name: The package name to normalize.

        Returns:
            Normalized package name.
        """
        return package_name

    def get_alternative_names(self, package_name: str) -> list[str]:
        """
        Get alternative names to try when looking up a package in Fedora.

        Some packages may be named differently in Fedora than in the upstream
        registry. Override this method to provide alternatives to try.

        Args:
            package_name: The original package name.

        Returns:
            List of alternative names to try.
        """
        return []

    # ----------------------------------------------------------------
    # Fedora repository query methods - shared implementation
    # ----------------------------------------------------------------

    def _repoquery_package(
        self, package_name: str
    ) -> tuple[bool, list[str], list[str]]:
        """
        Query Fedora for a package using the virtual provides pattern.

        Args:
            package_name: The name of the package to query.

        Returns:
            Tuple of (is_packaged, versions_list, package_names)
        """
        cache_key = f"repoquery:{self.name}:{package_name}"
        cached = read_cache("fedora", cache_key, FEDORA_CACHE_TTL)
        if cached is not None:
            log_cache_hit("fedora", cache_key)
            return tuple(cached)

        log_cache_miss("fedora", cache_key)
        provide_pattern = self.get_fedora_provides_pattern(package_name)
        cmd = [
            "dnf",
            "repoquery",
            "--whatprovides",
            provide_pattern,
            "--queryformat",
            "%{NAME}|%{VERSION}",
        ]

        try:
            out = (
                subprocess.check_output(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )

            log_command_output(" ".join(cmd), out, exit_code=0)

            if not out:
                result = (False, [], [])
                write_cache("fedora", cache_key, list(result))
                return result

            versions = set()
            packages = set()
            for line in out.split("\n"):
                if "|" in line:
                    pkg, ver = line.split("|", 1)
                    packages.add(pkg)
                    versions.add(ver)

            result = (True, sorted(versions), sorted(packages))
            write_cache("fedora", cache_key, [result[0], result[1], result[2]])
            return result
        except subprocess.CalledProcessError as e:
            log_command_output(" ".join(cmd), "", exit_code=e.returncode)
            result = (False, [], [])
            write_cache("fedora", cache_key, list(result))
            return result

    def _get_provides_version(self, package_name: str) -> list[str]:
        """
        Get the actual package version provided by Fedora packages.

        Args:
            package_name: The name of the package.

        Returns:
            List of version strings provided by Fedora packages.
        """
        cache_key = f"provides:{self.name}:{package_name}"
        cached = read_cache("fedora", cache_key, FEDORA_CACHE_TTL)
        if cached is not None:
            log_cache_hit("fedora", cache_key)
            return cached

        log_cache_miss("fedora", cache_key)
        provide_pattern = self.get_fedora_provides_pattern(package_name)
        normalized = self.normalize_package_name(package_name)
        cmd = ["dnf", "repoquery", "--provides", "--whatprovides", provide_pattern]

        try:
            out = (
                subprocess.check_output(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )

            log_command_output(" ".join(cmd), out, exit_code=0)

            if not out:
                write_cache("fedora", cache_key, [])
                return []

            versions = set()
            # Build pattern: prefix(normalized_name) = version
            pattern = re.compile(
                rf"{re.escape(self.fedora_provides_prefix)}\({re.escape(normalized)}\)\s*=\s*([\d.]+)"
            )
            for line in out.split("\n"):
                match = pattern.search(line)
                if match:
                    versions.add(match.group(1))

            result = sorted(versions)
            write_cache("fedora", cache_key, result)
            return result
        except subprocess.CalledProcessError as e:
            log_command_output(" ".join(cmd), "", exit_code=e.returncode)
            write_cache("fedora", cache_key, [])
            return []

    def check_fedora_packaging(self, package_name: str) -> FedoraPackageStatus:
        """
        Check if a package is available in Fedora repositories.

        This method queries Fedora repositories to determine if the
        package is packaged and what versions are available.

        Args:
            package_name: The name of the package.

        Returns:
            FedoraPackageStatus with packaging information.
        """
        normalized = self.normalize_package_name(package_name)
        is_packaged, pkg_versions, packages = self._repoquery_package(normalized)

        # Try alternative names if not found
        if not is_packaged:
            for alt_name in self.get_alternative_names(package_name):
                is_packaged, pkg_versions, packages = self._repoquery_package(alt_name)
                if is_packaged:
                    break

        if is_packaged:
            provided_versions = self._get_provides_version(normalized)
            if not provided_versions:
                provided_versions = pkg_versions
            return FedoraPackageStatus(
                is_packaged=True,
                versions=provided_versions,
                package_names=packages,
            )

        return FedoraPackageStatus(
            is_packaged=False,
            versions=[],
            package_names=[],
        )

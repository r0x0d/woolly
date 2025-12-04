"""
Unit tests for woolly.languages.base module.

Tests cover:
- Good path: base provider methods
- Critical path: Fedora packaging checks, dependency filtering
- Bad path: missing packages, subprocess failures
"""

import subprocess

import pytest

from woolly.languages.base import (
    Dependency,
    FedoraPackageStatus,
    LanguageProvider,
    PackageInfo,
)


class ConcreteProvider(LanguageProvider):
    """Concrete implementation for testing abstract base class."""

    name = "test"
    display_name = "Test"
    registry_name = "test.io"
    fedora_provides_prefix = "test"
    cache_namespace = "test"

    def __init__(self):
        self._package_info: PackageInfo | None = None
        self._dependencies: list[Dependency] = []

    def fetch_package_info(self, package_name: str):
        return self._package_info

    def fetch_dependencies(self, package_name: str, version: str):
        return self._dependencies


class TestPackageInfo:
    """Tests for PackageInfo model."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Good path: PackageInfo with required fields."""
        info = PackageInfo(name="test", latest_version="1.0.0")
        assert info.name == "test"
        assert info.latest_version == "1.0.0"

    @pytest.mark.unit
    def test_optional_fields(self):
        """Good path: PackageInfo with all fields."""
        info = PackageInfo(
            name="test",
            latest_version="1.0.0",
            description="A test package",
            homepage="https://example.com",
            repository="https://github.com/example/test",
        )
        assert info.description == "A test package"
        assert info.homepage == "https://example.com"

    @pytest.mark.unit
    def test_optional_fields_default_to_none(self):
        """Good path: optional fields are None by default."""
        info = PackageInfo(name="test", latest_version="1.0.0")
        assert info.description is None
        assert info.homepage is None
        assert info.repository is None


class TestDependency:
    """Tests for Dependency model."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Good path: Dependency with required fields."""
        dep = Dependency(name="dep", version_requirement=">=1.0")
        assert dep.name == "dep"
        assert dep.version_requirement == ">=1.0"

    @pytest.mark.unit
    def test_default_values(self):
        """Good path: Dependency default values."""
        dep = Dependency(name="dep", version_requirement="*")
        assert dep.optional is False
        assert dep.kind == "normal"

    @pytest.mark.unit
    def test_all_kinds(self):
        """Good path: all dependency kinds are valid."""
        from typing import Literal, get_args

        DependencyKind = Literal["normal", "dev", "build"]
        for kind in get_args(DependencyKind):
            dep = Dependency(name="dep", version_requirement="*", kind=kind)
            assert dep.kind == kind


class TestFedoraPackageStatus:
    """Tests for FedoraPackageStatus model."""

    @pytest.mark.unit
    def test_packaged_status(self):
        """Good path: packaged status with versions."""
        status = FedoraPackageStatus(
            is_packaged=True,
            versions=["1.0.0", "1.1.0"],
            package_names=["rust-serde"],
        )
        assert status.is_packaged is True
        assert "1.0.0" in status.versions
        assert "rust-serde" in status.package_names

    @pytest.mark.unit
    def test_not_packaged_status(self):
        """Good path: not packaged status."""
        status = FedoraPackageStatus(is_packaged=False)
        assert status.is_packaged is False
        assert status.versions == []
        assert status.package_names == []


class TestLanguageProviderGetLatestVersion:
    """Tests for LanguageProvider.get_latest_version method."""

    @pytest.mark.unit
    def test_returns_version_when_package_exists(self):
        """Good path: returns version for existing package."""
        provider = ConcreteProvider()
        provider._package_info = PackageInfo(name="test", latest_version="2.0.0")

        version = provider.get_latest_version("test")
        assert version == "2.0.0"

    @pytest.mark.unit
    def test_returns_none_when_package_not_found(self):
        """Bad path: returns None for non-existent package."""
        provider = ConcreteProvider()
        provider._package_info = None

        version = provider.get_latest_version("nonexistent")
        assert version is None


class TestLanguageProviderGetNormalDependencies:
    """Tests for LanguageProvider.get_normal_dependencies method."""

    @pytest.mark.unit
    def test_returns_normal_non_optional_deps(self):
        """Critical path: filters to normal, non-optional dependencies."""
        provider = ConcreteProvider()
        provider._package_info = PackageInfo(name="test", latest_version="1.0.0")
        provider._dependencies = [
            Dependency(
                name="normal-dep",
                version_requirement=">=1.0",
                kind="normal",
                optional=False,
            ),
            Dependency(
                name="optional-dep",
                version_requirement=">=1.0",
                kind="normal",
                optional=True,
            ),
            Dependency(
                name="dev-dep", version_requirement=">=1.0", kind="dev", optional=False
            ),
            Dependency(
                name="build-dep",
                version_requirement=">=1.0",
                kind="build",
                optional=False,
            ),
        ]

        deps = provider.get_normal_dependencies("test", "1.0.0")

        assert len(deps) == 1
        assert deps[0][0] == "normal-dep"

    @pytest.mark.unit
    def test_returns_empty_when_no_version(self):
        """Bad path: returns empty list when package not found."""
        provider = ConcreteProvider()
        provider._package_info = None

        deps = provider.get_normal_dependencies("nonexistent")
        assert deps == []

    @pytest.mark.unit
    def test_fetches_latest_version_if_not_provided(self):
        """Good path: fetches latest version when not specified."""
        provider = ConcreteProvider()
        provider._package_info = PackageInfo(name="test", latest_version="3.0.0")
        provider._dependencies = [
            Dependency(
                name="dep", version_requirement="*", kind="normal", optional=False
            ),
        ]

        deps = provider.get_normal_dependencies("test")  # No version specified
        assert len(deps) == 1


class TestLanguageProviderFedoraProvidesPattern:
    """Tests for LanguageProvider.get_fedora_provides_pattern method."""

    @pytest.mark.unit
    def test_builds_correct_pattern(self):
        """Good path: builds correct provides pattern."""
        provider = ConcreteProvider()
        pattern = provider.get_fedora_provides_pattern("my-package")
        assert pattern == "test(my-package)"

    @pytest.mark.unit
    def test_uses_normalized_name(self):
        """Critical path: uses normalized package name."""
        provider = ConcreteProvider()

        # Override normalize to test it's being used
        original_normalize = provider.normalize_package_name
        provider.normalize_package_name = (
            lambda package_name: package_name.lower().replace("-", "_")
        )

        pattern = provider.get_fedora_provides_pattern("My-Package")
        assert pattern == "test(my_package)"

        provider.normalize_package_name = original_normalize


class TestLanguageProviderNormalizeName:
    """Tests for LanguageProvider.normalize_package_name method."""

    @pytest.mark.unit
    def test_default_returns_unchanged(self):
        """Good path: default implementation returns name unchanged."""
        provider = ConcreteProvider()
        assert provider.normalize_package_name("My-Package") == "My-Package"


class TestLanguageProviderAlternativeNames:
    """Tests for LanguageProvider.get_alternative_names method."""

    @pytest.mark.unit
    def test_default_returns_empty(self):
        """Good path: default implementation returns empty list."""
        provider = ConcreteProvider()
        assert provider.get_alternative_names("package") == []


class TestLanguageProviderRepoqueryPackage:
    """Tests for LanguageProvider._repoquery_package method."""

    @pytest.mark.unit
    def test_returns_packaged_status(self, temp_cache_dir, mocker):
        """Good path: returns packaged status when package found."""
        provider = ConcreteProvider()

        mock_output = b"rust-test|1.0.0\nrust-test|1.1.0"
        mocker.patch("subprocess.check_output", return_value=mock_output)

        is_packaged, versions, packages = provider._repoquery_package("test")

        assert is_packaged is True
        assert "1.0.0" in versions
        assert "rust-test" in packages

    @pytest.mark.unit
    def test_returns_not_packaged_for_empty_output(self, temp_cache_dir, mocker):
        """Good path: returns not packaged when no output."""
        provider = ConcreteProvider()

        mocker.patch("subprocess.check_output", return_value=b"")

        is_packaged, versions, packages = provider._repoquery_package("nonexistent")

        assert is_packaged is False
        assert versions == []
        assert packages == []

    @pytest.mark.unit
    def test_returns_not_packaged_on_error(self, temp_cache_dir, mocker):
        """Bad path: returns not packaged on subprocess error."""
        provider = ConcreteProvider()

        mocker.patch(
            "subprocess.check_output",
            side_effect=subprocess.CalledProcessError(1, "dnf"),
        )

        is_packaged, versions, packages = provider._repoquery_package("test")

        assert is_packaged is False

    @pytest.mark.unit
    def test_uses_cache(self, temp_cache_dir, mocker):
        """Critical path: uses cached results."""
        provider = ConcreteProvider()

        mock_check_output = mocker.patch(
            "subprocess.check_output", return_value=b"rust-test|1.0.0"
        )

        # First call
        provider._repoquery_package("test")
        # Second call should use cache
        provider._repoquery_package("test")

        # Should only call subprocess once
        assert mock_check_output.call_count == 1


class TestLanguageProviderCheckFedoraPackaging:
    """Tests for LanguageProvider.check_fedora_packaging method."""

    @pytest.mark.unit
    def test_returns_packaged_status(self, temp_cache_dir, mocker):
        """Good path: returns correct status for packaged package."""
        provider = ConcreteProvider()

        mocker.patch("subprocess.check_output", return_value=b"rust-pkg|1.0.0")

        status = provider.check_fedora_packaging("pkg")

        assert isinstance(status, FedoraPackageStatus)
        assert status.is_packaged is True

    @pytest.mark.unit
    def test_tries_alternative_names(self, temp_cache_dir, mocker):
        """Critical path: tries alternative names when not found."""
        provider = ConcreteProvider()
        provider.get_alternative_names = lambda package_name: ["alt-name"]

        call_count = 0

        def mock_output(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b""  # First call returns empty
            return b"rust-alt|1.0.0"  # Second call (alternative) succeeds

        mocker.patch("subprocess.check_output", side_effect=mock_output)

        status = provider.check_fedora_packaging("original-name")

        assert status.is_packaged is True

    @pytest.mark.unit
    def test_returns_not_packaged_when_not_found(self, temp_cache_dir, mocker):
        """Good path: returns not packaged when package not found."""
        provider = ConcreteProvider()

        mocker.patch("subprocess.check_output", return_value=b"")

        status = provider.check_fedora_packaging("nonexistent")

        assert status.is_packaged is False
        assert status.versions == []
        assert status.package_names == []

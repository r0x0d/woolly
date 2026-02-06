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
    FeatureInfo,
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

    def fetch_features(self, package_name: str, version: str):
        return []


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
        assert info.license is None

    @pytest.mark.unit
    def test_license_field(self):
        """Good path: PackageInfo with license field."""
        info = PackageInfo(name="test", latest_version="1.0.0", license="MIT")
        assert info.license == "MIT"


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
        assert dep.group is None

    @pytest.mark.unit
    def test_group_field(self):
        """Good path: Dependency with group field."""
        dep = Dependency(name="dep", version_requirement="*", group="socks")
        assert dep.group == "socks"

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

    @pytest.mark.unit
    def test_includes_releasever_flag(self, temp_cache_dir, mocker):
        """Good path: includes --releasever when fedora_release is set."""
        provider = ConcreteProvider()
        provider.fedora_release = "41"

        mock_check_output = mocker.patch(
            "subprocess.check_output", return_value=b"rust-test|1.0.0"
        )

        provider._repoquery_package("test")

        cmd = mock_check_output.call_args[0][0]
        assert "--releasever=41" in cmd

    @pytest.mark.unit
    def test_includes_repo_flags(self, temp_cache_dir, mocker):
        """Good path: includes --repo flags when fedora_repos is set."""
        provider = ConcreteProvider()
        provider.fedora_repos = ["updates", "updates-testing"]

        mock_check_output = mocker.patch(
            "subprocess.check_output", return_value=b"rust-test|1.0.0"
        )

        provider._repoquery_package("test")

        cmd = mock_check_output.call_args[0][0]
        assert "--repo" in cmd
        assert "updates" in cmd
        assert "updates-testing" in cmd

    @pytest.mark.unit
    def test_includes_releasever_and_repo_flags(self, temp_cache_dir, mocker):
        """Good path: includes both --releasever and --repo when both are set."""
        provider = ConcreteProvider()
        provider.fedora_release = "42"
        provider.fedora_repos = ["fedora"]

        mock_check_output = mocker.patch(
            "subprocess.check_output", return_value=b"rust-test|2.0.0"
        )

        provider._repoquery_package("test")

        cmd = mock_check_output.call_args[0][0]
        assert "--releasever=42" in cmd
        assert "--repo" in cmd
        assert "fedora" in cmd

    @pytest.mark.unit
    def test_cache_key_differs_per_release(self, temp_cache_dir, mocker):
        """Critical path: different releases produce different cache entries."""
        provider = ConcreteProvider()

        mock_check_output = mocker.patch(
            "subprocess.check_output", return_value=b"rust-test|1.0.0"
        )

        # Query with release 41
        provider.fedora_release = "41"
        provider._repoquery_package("test")

        # Query with release 42 — should NOT use the cached result
        provider.fedora_release = "42"
        provider._repoquery_package("test")

        assert mock_check_output.call_count == 2

    @pytest.mark.unit
    def test_cache_key_differs_per_repos(self, temp_cache_dir, mocker):
        """Critical path: different repo selections produce different cache entries."""
        provider = ConcreteProvider()

        mock_check_output = mocker.patch(
            "subprocess.check_output", return_value=b"rust-test|1.0.0"
        )

        # Query with updates repo
        provider.fedora_repos = ["updates"]
        provider._repoquery_package("test")

        # Query with updates-testing repo — should NOT use the cached result
        provider.fedora_repos = ["updates-testing"]
        provider._repoquery_package("test")

        assert mock_check_output.call_count == 2


class TestLanguageProviderBuildDnfRepoqueryCmd:
    """Tests for LanguageProvider._build_dnf_repoquery_cmd helper."""

    @pytest.mark.unit
    def test_base_cmd_without_targeting(self):
        """Good path: returns plain dnf repoquery when no targeting set."""
        provider = ConcreteProvider()
        cmd = provider._build_dnf_repoquery_cmd(["--whatprovides", "test(pkg)"])
        assert cmd == ["dnf", "repoquery", "--whatprovides", "test(pkg)"]

    @pytest.mark.unit
    def test_cmd_with_releasever(self):
        """Good path: injects --releasever flag."""
        provider = ConcreteProvider()
        provider.fedora_release = "41"
        cmd = provider._build_dnf_repoquery_cmd(["--whatprovides", "test(pkg)"])
        assert cmd[2] == "--releasever=41"

    @pytest.mark.unit
    def test_cmd_with_repos(self):
        """Good path: injects --repo flags for each repo."""
        provider = ConcreteProvider()
        provider.fedora_repos = ["fedora", "updates-testing"]
        cmd = provider._build_dnf_repoquery_cmd(["--whatprovides", "test(pkg)"])
        # Should contain --repo fedora --repo updates-testing
        repo_pairs = list(zip(cmd, cmd[1:]))
        assert ("--repo", "fedora") in repo_pairs
        assert ("--repo", "updates-testing") in repo_pairs

    @pytest.mark.unit
    def test_cmd_with_both(self):
        """Good path: injects both --releasever and --repo flags."""
        provider = ConcreteProvider()
        provider.fedora_release = "rawhide"
        provider.fedora_repos = ["rawhide"]
        cmd = provider._build_dnf_repoquery_cmd(["--whatprovides", "test(pkg)"])
        assert "--releasever=rawhide" in cmd
        assert "--repo" in cmd
        assert "rawhide" in cmd


class TestLanguageProviderFedoraCacheSuffix:
    """Tests for LanguageProvider._fedora_cache_suffix helper."""

    @pytest.mark.unit
    def test_empty_when_no_targeting(self):
        """Good path: returns empty string when no targeting set."""
        provider = ConcreteProvider()
        assert provider._fedora_cache_suffix() == ""

    @pytest.mark.unit
    def test_includes_release(self):
        """Good path: includes release in suffix."""
        provider = ConcreteProvider()
        provider.fedora_release = "41"
        assert provider._fedora_cache_suffix() == "rel=41"

    @pytest.mark.unit
    def test_includes_repos(self):
        """Good path: includes repos in suffix."""
        provider = ConcreteProvider()
        provider.fedora_repos = ["updates", "fedora"]
        suffix = provider._fedora_cache_suffix()
        # Repos should be sorted
        assert suffix == "repos=fedora,updates"

    @pytest.mark.unit
    def test_includes_both(self):
        """Good path: includes both release and repos."""
        provider = ConcreteProvider()
        provider.fedora_release = "42"
        provider.fedora_repos = ["updates-testing"]
        suffix = provider._fedora_cache_suffix()
        assert suffix == "rel=42:repos=updates-testing"


class TestLanguageProviderGetProvidesVersionTargeting:
    """Tests for _get_provides_version with Fedora release/repo targeting."""

    @pytest.mark.unit
    def test_includes_releasever_flag(self, temp_cache_dir, mocker):
        """Good path: includes --releasever when fedora_release is set."""
        provider = ConcreteProvider()
        provider.fedora_release = "41"

        mock_check_output = mocker.patch(
            "subprocess.check_output",
            return_value=b"test(pkg) = 1.0.0",
        )

        provider._get_provides_version("pkg")

        cmd = mock_check_output.call_args[0][0]
        assert "--releasever=41" in cmd

    @pytest.mark.unit
    def test_includes_repo_flags(self, temp_cache_dir, mocker):
        """Good path: includes --repo flags when fedora_repos is set."""
        provider = ConcreteProvider()
        provider.fedora_repos = ["updates-testing"]

        mock_check_output = mocker.patch(
            "subprocess.check_output",
            return_value=b"test(pkg) = 2.0.0",
        )

        provider._get_provides_version("pkg")

        cmd = mock_check_output.call_args[0][0]
        assert "--repo" in cmd
        assert "updates-testing" in cmd


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


class TestFeatureInfo:
    """Tests for FeatureInfo model."""

    @pytest.mark.unit
    def test_required_fields(self):
        """Good path: FeatureInfo with required fields."""
        feature = FeatureInfo(name="default")
        assert feature.name == "default"
        assert feature.dependencies == []

    @pytest.mark.unit
    def test_with_dependencies(self):
        """Good path: FeatureInfo with dependencies."""
        feature = FeatureInfo(name="derive", dependencies=["serde_derive"])
        assert feature.name == "derive"
        assert "serde_derive" in feature.dependencies


class TestLanguageProviderGetDevDependencies:
    """Tests for LanguageProvider.get_dev_dependencies method."""

    @pytest.mark.unit
    def test_returns_dev_deps_only(self):
        """Good path: returns only dev dependencies."""
        provider = ConcreteProvider()
        provider._package_info = PackageInfo(name="test", latest_version="1.0.0")
        provider._dependencies = [
            Dependency(name="normal-dep", version_requirement=">=1.0", kind="normal"),
            Dependency(name="dev-dep", version_requirement=">=1.0", kind="dev"),
            Dependency(name="build-dep", version_requirement=">=1.0", kind="build"),
        ]

        dev_deps = provider.get_dev_dependencies("test", "1.0.0")

        assert len(dev_deps) == 1
        assert dev_deps[0].name == "dev-dep"
        assert dev_deps[0].kind == "dev"

    @pytest.mark.unit
    def test_returns_empty_when_no_dev_deps(self):
        """Good path: returns empty list when no dev deps."""
        provider = ConcreteProvider()
        provider._package_info = PackageInfo(name="test", latest_version="1.0.0")
        provider._dependencies = [
            Dependency(name="normal-dep", version_requirement=">=1.0", kind="normal"),
        ]

        dev_deps = provider.get_dev_dependencies("test", "1.0.0")

        assert dev_deps == []

    @pytest.mark.unit
    def test_returns_empty_when_package_not_found(self):
        """Bad path: returns empty list when package not found."""
        provider = ConcreteProvider()
        provider._package_info = None

        dev_deps = provider.get_dev_dependencies("nonexistent")

        assert dev_deps == []


class TestLanguageProviderGetBuildDependencies:
    """Tests for LanguageProvider.get_build_dependencies method."""

    @pytest.mark.unit
    def test_returns_build_deps_only(self):
        """Good path: returns only build dependencies."""
        provider = ConcreteProvider()
        provider._package_info = PackageInfo(name="test", latest_version="1.0.0")
        provider._dependencies = [
            Dependency(name="normal-dep", version_requirement=">=1.0", kind="normal"),
            Dependency(name="dev-dep", version_requirement=">=1.0", kind="dev"),
            Dependency(name="build-dep", version_requirement=">=1.0", kind="build"),
        ]

        build_deps = provider.get_build_dependencies("test", "1.0.0")

        assert len(build_deps) == 1
        assert build_deps[0].name == "build-dep"
        assert build_deps[0].kind == "build"

    @pytest.mark.unit
    def test_returns_empty_when_package_not_found(self):
        """Bad path: returns empty list when package not found."""
        provider = ConcreteProvider()
        provider._package_info = None

        build_deps = provider.get_build_dependencies("nonexistent")

        assert build_deps == []

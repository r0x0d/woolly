"""
Unit tests for woolly.commands.check module.

Tests cover:
- Good path: tree building, stats collection
- Critical path: dependency traversal, visited tracking
- Bad path: unknown languages, max depth
"""

from unittest.mock import MagicMock

import pytest
from rich.tree import Tree

from woolly.commands.check import TreeStats, _compute_stats_from_visited, build_tree
from woolly.languages.base import (
    Dependency,
    FedoraPackageStatus,
    LanguageProvider,
    PackageInfo,
)


class MockProvider(LanguageProvider):
    """Mock provider for testing."""

    name = "mock"
    display_name = "Mock"
    registry_name = "mock.io"
    fedora_provides_prefix = "mock"
    cache_namespace = "mock"

    def __init__(self):
        self.packages = {}
        self.dependencies = {}
        self.fedora_status = {}

    def fetch_package_info(self, package_name: str):
        return self.packages.get(package_name)

    def fetch_dependencies(self, package_name: str, version: str):
        return self.dependencies.get(f"{package_name}:{version}", [])

    def fetch_features(self, package_name: str, version: str):
        return []

    def check_fedora_packaging(self, package_name: str):
        return self.fedora_status.get(
            package_name, FedoraPackageStatus(is_packaged=False)
        )


class TestBuildTree:
    """Tests for build_tree function."""

    @pytest.fixture
    def provider(self):
        """Create a mock provider."""
        p = MockProvider()
        # Set up a simple package
        p.packages["root"] = PackageInfo(name="root", latest_version="1.0.0")
        p.fedora_status["root"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"], package_names=["mock-root"]
        )
        return p

    @pytest.mark.unit
    def test_returns_tree_for_packaged_package(self, provider):
        """Good path: returns Tree for packaged package."""
        tree = build_tree(provider, "root")

        assert isinstance(tree, Tree)
        label = str(tree.label)
        assert "root" in label
        assert "packaged" in label

    @pytest.mark.unit
    def test_returns_tree_for_not_packaged_package(self, provider):
        """Good path: returns Tree for not packaged package."""
        provider.packages["missing"] = PackageInfo(
            name="missing", latest_version="1.0.0"
        )
        provider.fedora_status["missing"] = FedoraPackageStatus(is_packaged=False)

        tree = build_tree(provider, "missing")

        assert isinstance(tree, Tree)
        label = str(tree.label)
        assert "not packaged" in label

    @pytest.mark.unit
    def test_returns_string_for_not_found_package(self, provider):
        """Bad path: returns string for package not in registry."""
        result = build_tree(provider, "nonexistent")

        assert isinstance(result, str)
        assert "not found" in result

    @pytest.mark.unit
    def test_tracks_visited_packages(self, provider):
        """Critical path: tracks visited packages."""
        visited = {}

        build_tree(provider, "root", visited=visited)

        assert "root" in visited
        assert visited["root"][0] is True  # is_packaged

    @pytest.mark.unit
    def test_returns_visited_marker_for_duplicate(self, provider):
        """Critical path: returns visited marker for already-visited packages."""
        visited = {"root": (True, "1.0.0", False)}

        result = build_tree(provider, "root", visited=visited)

        assert isinstance(result, str)
        assert "already visited" in result

    @pytest.mark.unit
    def test_respects_max_depth(self, provider):
        """Critical path: respects max depth limit."""
        result = build_tree(provider, "root", depth=100, max_depth=50)

        assert isinstance(result, str)
        assert "max depth" in result

    @pytest.mark.unit
    def test_recurses_into_dependencies(self, provider):
        """Critical path: recurses into dependencies."""
        # Set up package with dependency
        provider.packages["parent"] = PackageInfo(name="parent", latest_version="1.0.0")
        provider.packages["child"] = PackageInfo(name="child", latest_version="2.0.0")
        provider.dependencies["parent:1.0.0"] = [
            Dependency(name="child", version_requirement="^2.0", kind="normal")
        ]
        provider.fedora_status["parent"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )
        provider.fedora_status["child"] = FedoraPackageStatus(
            is_packaged=True, versions=["2.0.0"]
        )

        tree = build_tree(provider, "parent")

        # Should have a child
        assert isinstance(tree, Tree)
        assert len(tree.children) > 0

    @pytest.mark.unit
    def test_uses_provided_version(self, provider):
        """Good path: uses provided version instead of latest."""
        provider.packages["pkg"] = PackageInfo(name="pkg", latest_version="2.0.0")
        provider.fedora_status["pkg"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )

        tree = build_tree(provider, "pkg", version="1.0.0")

        assert isinstance(tree, Tree)
        label = str(tree.label)
        assert "1.0.0" in label

    @pytest.mark.unit
    def test_includes_license_in_label(self, provider):
        """Good path: license is shown in tree label."""
        provider.packages["licensed-pkg"] = PackageInfo(
            name="licensed-pkg", latest_version="1.0.0", license="MIT"
        )
        provider.fedora_status["licensed-pkg"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )

        tree = build_tree(provider, "licensed-pkg")

        assert isinstance(tree, Tree)
        label = str(tree.label)
        assert "MIT" in label

    @pytest.mark.unit
    def test_no_license_marker_when_no_license(self, provider):
        """Good path: no license marker when package has no license."""
        tree = build_tree(provider, "root")

        assert isinstance(tree, Tree)
        label = str(tree.label)
        # License info from mock_package_info is None, so no license marker
        assert "(None)" not in label

    @pytest.mark.unit
    def test_updates_progress_tracker(self, provider):
        """Good path: updates progress tracker when provided."""
        tracker = MagicMock()
        provider.packages["pkg"] = PackageInfo(name="pkg", latest_version="1.0.0")
        provider.fedora_status["pkg"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )

        build_tree(provider, "pkg", tracker=tracker)

        tracker.update.assert_called()

    @pytest.mark.unit
    def test_excludes_dependencies_matching_pattern(self, provider):
        """Good path: excludes dependencies matching glob patterns."""
        # Set up package with dependencies
        provider.packages["parent"] = PackageInfo(name="parent", latest_version="1.0.0")
        provider.packages["child"] = PackageInfo(name="child", latest_version="2.0.0")
        provider.packages["windows-sys"] = PackageInfo(
            name="windows-sys", latest_version="0.52.0"
        )
        provider.dependencies["parent:1.0.0"] = [
            Dependency(name="child", version_requirement="^2.0", kind="normal"),
            Dependency(name="windows-sys", version_requirement="^0.52", kind="normal"),
        ]
        provider.fedora_status["parent"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )
        provider.fedora_status["child"] = FedoraPackageStatus(
            is_packaged=True, versions=["2.0.0"]
        )
        provider.fedora_status["windows-sys"] = FedoraPackageStatus(is_packaged=False)

        tree = build_tree(provider, "parent", exclude_patterns=["windows*"])

        # Should only have child, not windows-sys
        assert isinstance(tree, Tree)
        assert len(tree.children) == 1
        child_label = str(tree.children[0].label)
        assert "child" in child_label
        # windows-sys should be excluded
        for child in tree.children:
            label = str(child.label) if hasattr(child, "label") else str(child)
            assert "windows" not in label

    @pytest.mark.unit
    def test_excludes_multiple_patterns(self, provider):
        """Good path: excludes dependencies matching multiple glob patterns."""
        provider.packages["parent"] = PackageInfo(name="parent", latest_version="1.0.0")
        provider.packages["good-dep"] = PackageInfo(
            name="good-dep", latest_version="1.0.0"
        )
        provider.packages["win-dep"] = PackageInfo(
            name="win-dep", latest_version="1.0.0"
        )
        provider.packages["macos-dep"] = PackageInfo(
            name="macos-dep", latest_version="1.0.0"
        )
        provider.dependencies["parent:1.0.0"] = [
            Dependency(name="good-dep", version_requirement="^1.0", kind="normal"),
            Dependency(name="win-dep", version_requirement="^1.0", kind="normal"),
            Dependency(name="macos-dep", version_requirement="^1.0", kind="normal"),
        ]
        provider.fedora_status["parent"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )
        provider.fedora_status["good-dep"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )
        provider.fedora_status["win-dep"] = FedoraPackageStatus(is_packaged=False)
        provider.fedora_status["macos-dep"] = FedoraPackageStatus(is_packaged=False)

        tree = build_tree(provider, "parent", exclude_patterns=["win*", "macos*"])

        # Should only have good-dep
        assert isinstance(tree, Tree)
        assert len(tree.children) == 1
        child_label = str(tree.children[0].label)
        assert "good-dep" in child_label

    @pytest.mark.unit
    def test_exclude_patterns_applied_recursively(self, provider):
        """Good path: exclude patterns are applied at all depth levels."""
        provider.packages["root"] = PackageInfo(name="root", latest_version="1.0.0")
        provider.packages["child"] = PackageInfo(name="child", latest_version="1.0.0")
        provider.packages["windows-inner"] = PackageInfo(
            name="windows-inner", latest_version="1.0.0"
        )
        provider.dependencies["root:1.0.0"] = [
            Dependency(name="child", version_requirement="^1.0", kind="normal"),
        ]
        provider.dependencies["child:1.0.0"] = [
            Dependency(name="windows-inner", version_requirement="^1.0", kind="normal"),
        ]
        provider.fedora_status["root"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )
        provider.fedora_status["child"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )
        provider.fedora_status["windows-inner"] = FedoraPackageStatus(is_packaged=False)

        tree = build_tree(provider, "root", exclude_patterns=["windows*"])

        # root -> child (no windows-inner)
        assert isinstance(tree, Tree)
        assert len(tree.children) == 1
        child_tree = tree.children[0]
        assert isinstance(child_tree, Tree)
        # child should have no children (windows-inner was filtered)
        assert len(child_tree.children) == 0

    @pytest.mark.unit
    def test_no_exclusion_when_patterns_none(self, provider):
        """Good path: no exclusion when patterns is None."""
        provider.packages["parent"] = PackageInfo(name="parent", latest_version="1.0.0")
        provider.packages["child"] = PackageInfo(name="child", latest_version="1.0.0")
        provider.dependencies["parent:1.0.0"] = [
            Dependency(name="child", version_requirement="^1.0", kind="normal"),
        ]
        provider.fedora_status["parent"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )
        provider.fedora_status["child"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"]
        )

        tree = build_tree(provider, "parent", exclude_patterns=None)

        assert isinstance(tree, Tree)
        assert len(tree.children) == 1


class TestComputeStatsFromVisited:
    """Tests for _compute_stats_from_visited function."""

    @pytest.mark.unit
    def test_returns_tree_stats_model(self):
        """Good path: returns TreeStats model."""
        visited = {"root": (True, "1.0.0", False)}

        stats = _compute_stats_from_visited(visited)

        assert isinstance(stats, TreeStats)

    @pytest.mark.unit
    def test_counts_packaged(self):
        """Good path: counts packaged packages."""
        visited = {"root": (True, "1.0.0", False)}

        stats = _compute_stats_from_visited(visited)

        assert stats.packaged == 1

    @pytest.mark.unit
    def test_counts_missing(self):
        """Good path: counts missing packages."""
        visited = {"root": (False, "1.0.0", False)}

        stats = _compute_stats_from_visited(visited)

        assert stats.missing == 1

    @pytest.mark.unit
    def test_collects_missing_list(self):
        """Good path: collects list of missing packages."""
        visited = {"missing-pkg": (False, "1.0.0", False)}

        stats = _compute_stats_from_visited(visited)

        assert len(stats.missing_list) == 1
        assert "missing-pkg" in stats.missing_list

    @pytest.mark.unit
    def test_collects_packaged_list(self):
        """Good path: collects list of packaged packages."""
        visited = {"pkg": (True, "1.0.0", False)}

        stats = _compute_stats_from_visited(visited)

        assert len(stats.packaged_list) == 1
        assert "pkg" in stats.packaged_list

    @pytest.mark.unit
    def test_counts_not_found_as_missing(self):
        """Good path: counts not-found packages (version=None) as missing."""
        visited = {"unknown": (False, None, False)}

        stats = _compute_stats_from_visited(visited)

        assert stats.missing == 1
        assert "unknown" in stats.missing_list

    @pytest.mark.unit
    def test_multiple_packages(self):
        """Critical path: counts all packages from visited dict."""
        visited = {
            "root": (True, "1.0.0", False),
            "child1": (True, "1.0.0", False),
            "child2": (False, "1.0.0", False),
        }

        stats = _compute_stats_from_visited(visited)

        assert stats.total == 3
        assert stats.packaged == 2
        assert stats.missing == 1

    @pytest.mark.unit
    def test_empty_visited(self):
        """Good path: handles empty visited dict."""
        stats = _compute_stats_from_visited({})

        assert stats.total == 0
        assert stats.packaged == 0
        assert stats.missing == 0
        assert stats.missing_list == []
        assert stats.packaged_list == []

    @pytest.mark.unit
    def test_has_dev_build_stats(self):
        """Good path: stats model has dev/build dependency stats (zeroed by default)."""
        visited = {"pkg": (True, "1.0.0", False)}

        stats = _compute_stats_from_visited(visited)

        assert hasattr(stats, "dev_total")
        assert hasattr(stats, "dev_packaged")
        assert hasattr(stats, "dev_missing")
        assert hasattr(stats, "build_total")
        assert hasattr(stats, "build_packaged")
        assert hasattr(stats, "build_missing")
        assert stats.dev_total == 0
        assert stats.build_total == 0

    @pytest.mark.unit
    def test_optional_dependency_tracking(self):
        """Good path: tracks optional dependency statistics."""
        visited = {
            "required": (True, "1.0.0", False),
            "opt-packaged": (True, "2.0.0", True),
            "opt-missing": (False, "3.0.0", True),
        }

        stats = _compute_stats_from_visited(visited)

        assert stats.total == 3
        assert stats.optional_total == 2
        assert stats.optional_packaged == 1
        assert stats.optional_missing == 1
        assert "opt-missing" in stats.optional_missing_list

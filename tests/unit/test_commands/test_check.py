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

from woolly.commands.check import TreeStats, build_tree, collect_stats
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
        visited = {"root": (True, "1.0.0")}

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


class TestCollectStats:
    """Tests for collect_stats function."""

    @pytest.mark.unit
    def test_returns_tree_stats_model(self):
        """Good path: returns TreeStats model."""
        tree = Tree("[bold]root[/bold] v1.0.0 • [green]✓ packaged[/green]")

        stats = collect_stats(tree)

        assert isinstance(stats, TreeStats)

    @pytest.mark.unit
    def test_counts_packaged(self):
        """Good path: counts packaged packages."""
        tree = Tree("[bold]root[/bold] v1.0.0 • [green]✓ packaged[/green]")

        stats = collect_stats(tree)

        assert stats.packaged >= 1

    @pytest.mark.unit
    def test_counts_missing(self):
        """Good path: counts missing packages."""
        tree = Tree("[bold]root[/bold] v1.0.0 • [red]✗ not packaged[/red]")

        stats = collect_stats(tree)

        assert stats.missing >= 1

    @pytest.mark.unit
    def test_collects_missing_list(self):
        """Good path: collects list of missing packages."""
        tree = Tree("[bold]missing-pkg[/bold] v1.0.0 • [red]✗ not packaged[/red]")

        stats = collect_stats(tree)

        assert len(stats.missing_list) >= 1

    @pytest.mark.unit
    def test_collects_packaged_list(self):
        """Good path: collects list of packaged packages."""
        tree = Tree("[bold]pkg[/bold] v1.0.0 • [green]✓ packaged[/green]")

        stats = collect_stats(tree)

        assert len(stats.packaged_list) >= 1

    @pytest.mark.unit
    def test_handles_string_children(self):
        """Good path: handles string children (visited markers)."""
        tree = Tree("[bold]root[/bold]")
        tree.add("[dim]child[/dim] • [green]✓[/green] (already visited)")

        stats = collect_stats(tree)

        assert stats.total >= 1

    @pytest.mark.unit
    def test_counts_not_found_as_missing(self):
        """Good path: counts 'not found' as missing."""
        tree = Tree("[bold]unknown[/bold] • [red]not found on registry[/red]")

        stats = collect_stats(tree)

        assert stats.missing >= 1

    @pytest.mark.unit
    def test_extracts_name_from_not_found_string(self):
        """Bug fix: correctly extracts package name from 'not found' string with [bold red] format."""
        # This is the format returned by build_tree when a package is not found on the registry
        tree = Tree("[bold]root[/bold] v1.0.0 • [green]✓ packaged[/green]")
        # Add a child that represents a package not found on the registry (string format)
        tree.add(
            "[bold red]nonexistent-pkg[/bold red] • [red]not found on crates.io[/red]"
        )

        stats = collect_stats(tree)

        assert stats.missing == 1
        assert "nonexistent-pkg" in stats.missing_list
        # Ensure we don't have malformed names like "[bold"
        for name in stats.missing_list:
            assert not name.startswith("["), f"Malformed package name: {name}"

    @pytest.mark.unit
    def test_recursive_counting(self):
        """Critical path: counts all nodes recursively."""
        root = Tree("[bold]root[/bold] v1.0.0 • [green]✓ packaged[/green]")
        child1 = Tree("[bold]child1[/bold] v1.0.0 • [green]✓ packaged[/green]")
        child2 = Tree("[bold]child2[/bold] v1.0.0 • [red]✗ not packaged[/red]")
        root.children.append(child1)
        root.children.append(child2)

        stats = collect_stats(root)

        assert stats.total == 3
        assert stats.packaged == 2
        assert stats.missing == 1

    @pytest.mark.unit
    def test_initializes_stats_if_not_provided(self):
        """Good path: initializes stats model if not provided."""
        tree = Tree("[bold]pkg[/bold]")

        stats = collect_stats(tree)

        assert hasattr(stats, "total")
        assert hasattr(stats, "packaged")
        assert hasattr(stats, "missing")
        assert hasattr(stats, "missing_list")
        assert hasattr(stats, "packaged_list")

"""
Unit tests for optional dependencies functionality.

Tests cover:
- Good path: including optional dependencies when flag is set
- Critical path: optional marker propagation through tree
- Bad path: excluding optional dependencies by default
"""

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


class TestGetNormalDependencies:
    """Tests for the get_normal_dependencies method with optional support."""

    @pytest.fixture
    def provider(self):
        """Create a mock provider."""
        p = MockProvider()
        p.packages["test-pkg"] = PackageInfo(name="test-pkg", latest_version="1.0.0")
        p.dependencies["test-pkg:1.0.0"] = [
            Dependency(
                name="required-dep",
                version_requirement="^1.0",
                kind="normal",
                optional=False,
            ),
            Dependency(
                name="optional-dep",
                version_requirement="^2.0",
                kind="normal",
                optional=True,
            ),
            Dependency(
                name="another-required",
                version_requirement="^3.0",
                kind="normal",
                optional=False,
            ),
            Dependency(
                name="dev-dep", version_requirement="*", kind="dev", optional=False
            ),
            Dependency(
                name="build-dep",
                version_requirement="^1.0",
                kind="build",
                optional=False,
            ),
        ]
        return p

    @pytest.mark.unit
    def test_excludes_optional_by_default(self, provider):
        """Bad path: optional dependencies are excluded by default."""
        result = provider.get_normal_dependencies("test-pkg")

        # Should only include required normal dependencies
        assert len(result) == 2
        names = [r[0] for r in result]
        assert "required-dep" in names
        assert "another-required" in names
        assert "optional-dep" not in names

    @pytest.mark.unit
    def test_includes_optional_when_flag_set(self, provider):
        """Good path: optional dependencies are included when flag is set."""
        result = provider.get_normal_dependencies("test-pkg", include_optional=True)

        # Should include all normal dependencies including optional
        assert len(result) == 3
        names = [r[0] for r in result]
        assert "required-dep" in names
        assert "optional-dep" in names
        assert "another-required" in names

    @pytest.mark.unit
    def test_returns_is_optional_flag_in_tuple(self, provider):
        """Good path: returns is_optional flag in tuple."""
        result = provider.get_normal_dependencies("test-pkg", include_optional=True)

        # Find the optional dep
        optional_result = [r for r in result if r[0] == "optional-dep"]
        assert len(optional_result) == 1
        name, req, is_optional = optional_result[0]
        assert name == "optional-dep"
        assert is_optional is True

        # Find a required dep
        required_result = [r for r in result if r[0] == "required-dep"]
        assert len(required_result) == 1
        name, req, is_optional = required_result[0]
        assert name == "required-dep"
        assert is_optional is False

    @pytest.mark.unit
    def test_ignores_dev_dependencies(self, provider):
        """Critical path: dev dependencies are always ignored."""
        result = provider.get_normal_dependencies("test-pkg", include_optional=True)

        names = [r[0] for r in result]
        assert "dev-dep" not in names

    @pytest.mark.unit
    def test_ignores_build_dependencies(self, provider):
        """Critical path: build dependencies are always ignored."""
        result = provider.get_normal_dependencies("test-pkg", include_optional=True)

        names = [r[0] for r in result]
        assert "build-dep" not in names

    @pytest.mark.unit
    def test_returns_empty_when_crate_not_found(self, provider):
        """Bad path: returns empty list for unknown package."""
        result = provider.get_normal_dependencies("nonexistent")

        assert result == []


class TestBuildTreeOptional:
    """Tests for build_tree function with optional dependencies."""

    @pytest.fixture
    def provider(self):
        """Create a mock provider with optional dependencies."""
        p = MockProvider()
        # Parent package
        p.packages["parent"] = PackageInfo(name="parent", latest_version="1.0.0")
        p.fedora_status["parent"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"], package_names=["mock-parent"]
        )
        # Required child
        p.packages["required-child"] = PackageInfo(
            name="required-child", latest_version="1.0.0"
        )
        p.fedora_status["required-child"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"], package_names=["mock-required-child"]
        )
        # Optional child - packaged
        p.packages["optional-child"] = PackageInfo(
            name="optional-child", latest_version="1.0.0"
        )
        p.fedora_status["optional-child"] = FedoraPackageStatus(
            is_packaged=True, versions=["1.0.0"], package_names=["mock-optional-child"]
        )
        # Optional child - not packaged
        p.packages["optional-missing"] = PackageInfo(
            name="optional-missing", latest_version="1.0.0"
        )
        p.fedora_status["optional-missing"] = FedoraPackageStatus(is_packaged=False)

        # Set up dependencies
        p.dependencies["parent:1.0.0"] = [
            Dependency(
                name="required-child",
                version_requirement="^1.0",
                kind="normal",
                optional=False,
            ),
            Dependency(
                name="optional-child",
                version_requirement="^1.0",
                kind="normal",
                optional=True,
            ),
            Dependency(
                name="optional-missing",
                version_requirement="^1.0",
                kind="normal",
                optional=True,
            ),
        ]
        return p

    @pytest.mark.unit
    def test_build_tree_without_optional(self, provider):
        """Bad path: build_tree excludes optional deps by default."""
        tree = build_tree(provider, "parent")

        assert isinstance(tree, Tree)
        # Should only have required child
        assert len(tree.children) == 1

    @pytest.mark.unit
    def test_build_tree_with_optional(self, provider):
        """Good path: build_tree includes optional deps when flag is set."""
        tree = build_tree(provider, "parent", include_optional=True)

        assert isinstance(tree, Tree)
        # Should have all 3 children: required + 2 optional
        assert len(tree.children) == 3

    @pytest.mark.unit
    def test_optional_marker_in_tree_label(self, provider):
        """Good path: optional dependencies are marked in the tree."""
        tree = build_tree(provider, "parent", include_optional=True)

        assert isinstance(tree, Tree)
        # Find optional children
        optional_count = 0
        for child in tree.children:
            if isinstance(child, Tree):
                label = str(child.label)
            else:
                label = str(child)
            if "(optional)" in label:
                optional_count += 1

        assert optional_count == 2  # optional-child and optional-missing

    @pytest.mark.unit
    def test_no_optional_marker_for_required(self, provider):
        """Good path: required dependencies don't have optional marker."""
        tree = build_tree(provider, "parent", include_optional=True)

        assert isinstance(tree, Tree)
        # The root should not have optional marker
        label = str(tree.label)
        assert "(optional)" not in label

    @pytest.mark.unit
    def test_optional_marker_propagates_through_is_optional_dep(self, provider):
        """Critical path: is_optional_dep parameter adds marker."""
        tree = build_tree(provider, "required-child", is_optional_dep=True)

        assert isinstance(tree, Tree)
        label = str(tree.label)
        assert "(optional)" in label

    @pytest.mark.unit
    def test_optional_marker_in_not_found_message(self, provider):
        """Critical path: optional marker appears in 'not found' message."""
        result = build_tree(provider, "nonexistent-pkg", is_optional_dep=True)

        assert isinstance(result, str)
        assert "(optional)" in result
        assert "not found" in result

    @pytest.mark.unit
    def test_optional_marker_in_max_depth_message(self, provider):
        """Critical path: optional marker appears when max depth is reached."""
        result = build_tree(
            provider, "parent", depth=100, max_depth=50, is_optional_dep=True
        )

        assert isinstance(result, str)
        assert "(optional)" in result
        assert "max depth" in result

    @pytest.mark.unit
    def test_optional_marker_in_already_visited(self, provider):
        """Critical path: optional marker appears for already visited packages."""
        visited = {"parent": (True, "1.0.0")}

        result = build_tree(provider, "parent", visited=visited, is_optional_dep=True)

        assert isinstance(result, str)
        assert "(optional)" in result
        assert "already visited" in result


class TestCollectStatsOptional:
    """Tests for collect_stats function with optional dependencies."""

    @pytest.mark.unit
    def test_counts_optional_dependencies(self):
        """Good path: optional dependencies are counted separately."""
        root = Tree("[bold]root[/bold] v1.0 • [green]✓ packaged[/green]")
        root.add("[bold]required-dep[/bold] v1.0 • [red]✗ not packaged[/red]")
        root.add(
            "[bold]optional-dep[/bold] v1.0 [yellow](optional)[/yellow] • [red]✗ not packaged[/red]"
        )
        root.add(
            "[bold]optional-packaged[/bold] v1.0 [yellow](optional)[/yellow] • [green]✓ packaged[/green]"
        )

        stats = collect_stats(root)

        assert stats.total == 4
        assert stats.optional_total == 2
        assert stats.optional_missing == 1
        assert stats.optional_packaged == 1
        assert len(stats.optional_missing_list) == 1

    @pytest.mark.unit
    def test_empty_tree_stats(self):
        """Good path: stats for tree with no optional deps."""
        root = Tree("[bold]root[/bold] v1.0 • [green]✓ packaged[/green]")

        stats = collect_stats(root)

        assert stats.total == 1
        assert stats.optional_total == 0
        assert stats.optional_missing == 0
        assert stats.optional_packaged == 0

    @pytest.mark.unit
    def test_stats_include_string_nodes(self):
        """Good path: string nodes (already visited, max depth) are counted."""
        root = Tree("[bold]root[/bold] v1.0 • [green]✓ packaged[/green]")
        root.add("[dim]visited-dep [yellow](optional)[/yellow] (already visited)[/dim]")

        stats = collect_stats(root)

        assert stats.total == 2
        assert stats.optional_total == 1

    @pytest.mark.unit
    def test_stats_has_all_required_attributes(self):
        """Good path: stats model has all required attributes."""
        root = Tree("[bold]root[/bold] v1.0 • [green]✓ packaged[/green]")

        stats = collect_stats(root)

        assert isinstance(stats, TreeStats)
        required_attrs = [
            "total",
            "packaged",
            "missing",
            "missing_list",
            "packaged_list",
            "optional_total",
            "optional_packaged",
            "optional_missing",
            "optional_missing_list",
        ]
        for attr in required_attrs:
            assert hasattr(stats, attr), f"Missing attribute: {attr}"

    @pytest.mark.unit
    def test_recursive_counting_with_optional(self):
        """Critical path: counts all nodes recursively including optional."""
        root = Tree("[bold]root[/bold] v1.0 • [green]✓ packaged[/green]")
        child1 = Tree("[bold]child1[/bold] v1.0 • [green]✓ packaged[/green]")
        child2 = Tree(
            "[bold]child2[/bold] v1.0 [yellow](optional)[/yellow] • [red]✗ not packaged[/red]"
        )
        grandchild = Tree(
            "[bold]grandchild[/bold] v1.0 [yellow](optional)[/yellow] • [green]✓ packaged[/green]"
        )
        child2.children.append(grandchild)
        root.children.append(child1)
        root.children.append(child2)

        stats = collect_stats(root)

        assert stats.total == 4
        assert stats.packaged == 3
        assert stats.missing == 1
        assert stats.optional_total == 2
        assert stats.optional_packaged == 1
        assert stats.optional_missing == 1

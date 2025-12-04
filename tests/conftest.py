"""
Shared pytest fixtures for woolly tests.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from rich.console import Console
from rich.tree import Tree

from woolly.languages.base import Dependency, FedoraPackageStatus, PackageInfo
from woolly.reporters.base import ReportData


# ============================================================================
# Path and directory fixtures
# ============================================================================


@pytest.fixture
def temp_cache_dir(tmp_path, monkeypatch):
    """Create a temporary cache directory and patch CACHE_DIR."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr("woolly.cache.CACHE_DIR", cache_dir)
    return cache_dir


@pytest.fixture
def temp_log_dir(tmp_path, monkeypatch):
    """Create a temporary log directory and patch LOG_DIR."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr("woolly.debug.LOG_DIR", log_dir)
    return log_dir


# ============================================================================
# Package info fixtures
# ============================================================================


@pytest.fixture
def sample_package_info():
    """Create a sample PackageInfo for testing."""
    return PackageInfo(
        name="test-package",
        latest_version="1.0.0",
        description="A test package",
        homepage="https://example.com",
        repository="https://github.com/example/test-package",
    )


@pytest.fixture
def sample_dependency():
    """Create a sample Dependency for testing."""
    return Dependency(
        name="dep-package",
        version_requirement=">=1.0.0",
        optional=False,
        kind="normal",
    )


@pytest.fixture
def sample_dependencies():
    """Create a list of sample dependencies."""
    return [
        Dependency(
            name="dep-a", version_requirement=">=1.0.0", optional=False, kind="normal"
        ),
        Dependency(
            name="dep-b", version_requirement="^2.0", optional=False, kind="normal"
        ),
        Dependency(name="dev-dep", version_requirement="*", optional=True, kind="dev"),
        Dependency(
            name="build-dep",
            version_requirement=">=0.1.0",
            optional=False,
            kind="build",
        ),
    ]


@pytest.fixture
def fedora_packaged_status():
    """Create a FedoraPackageStatus for a packaged package."""
    return FedoraPackageStatus(
        is_packaged=True,
        versions=["1.0.0", "1.1.0"],
        package_names=["rust-test-package"],
    )


@pytest.fixture
def fedora_not_packaged_status():
    """Create a FedoraPackageStatus for a non-packaged package."""
    return FedoraPackageStatus(
        is_packaged=False,
        versions=[],
        package_names=[],
    )


# ============================================================================
# Mock API response fixtures
# ============================================================================


@pytest.fixture
def mock_crates_io_response():
    """Create a mock crates.io API response."""
    return {
        "crate": {
            "name": "serde",
            "newest_version": "1.0.200",
            "description": "A serialization framework for Rust",
            "homepage": "https://serde.rs",
            "repository": "https://github.com/serde-rs/serde",
        }
    }


@pytest.fixture
def mock_crates_io_deps_response():
    """Create a mock crates.io dependencies response."""
    return {
        "dependencies": [
            {
                "crate_id": "serde_derive",
                "req": "^1.0",
                "optional": True,
                "kind": "normal",
            },
            {
                "crate_id": "proc-macro2",
                "req": "^1.0",
                "optional": False,
                "kind": "dev",
            },
        ]
    }


@pytest.fixture
def mock_pypi_response():
    """Create a mock PyPI API response."""
    return {
        "info": {
            "name": "requests",
            "version": "2.31.0",
            "summary": "Python HTTP for Humans",
            "home_page": "https://requests.readthedocs.io",
            "project_url": "https://github.com/psf/requests",
            "requires_dist": [
                "charset-normalizer<4,>=2",
                "idna<4,>=2.5",
                "urllib3<3,>=1.21.1",
                "certifi>=2017.4.17",
                "PySocks!=1.5.7,>=1.5.6; extra == 'socks'",
            ],
        }
    }


# ============================================================================
# Reporter fixtures
# ============================================================================


@pytest.fixture
def mock_console():
    """Create a mock Rich console."""
    console = MagicMock(spec=Console)
    return console


@pytest.fixture
def sample_tree():
    """Create a sample Rich Tree for testing."""
    tree = Tree(
        "[bold]root-package[/bold] [dim]v1.0.0[/dim] • [green]✓ packaged[/green] [dim](1.0.0)[/dim]"
    )
    child1 = Tree(
        "[bold]dep-a[/bold] [dim]v2.0.0[/dim] • [green]✓ packaged[/green] [dim](2.0.0)[/dim]"
    )
    tree.add("[bold]dep-b[/bold] [dim]v1.5.0[/dim] • [red]✗ not packaged[/red]")
    tree.children.append(child1)
    return tree


@pytest.fixture
def sample_report_data(sample_tree):
    """Create a sample ReportData for testing."""
    return ReportData(
        root_package="test-package",
        language="Rust",
        registry="crates.io",
        total_dependencies=5,
        packaged_count=3,
        missing_count=2,
        missing_packages=["missing-a", "missing-b"],
        packaged_packages=["packaged-a", "packaged-b", "packaged-c"],
        tree=sample_tree,
        max_depth=50,
        version="1.0.0",
        timestamp=datetime(2024, 1, 15, 12, 0, 0),
    )


# ============================================================================
# HTTP response helper fixtures
# ============================================================================


@pytest.fixture
def make_httpx_response():
    """Factory to create mock httpx responses."""

    def _make_response(status_code: int, json_data=None, text: str = ""):
        response = MagicMock()
        response.status_code = status_code
        response.text = text or (str(json_data) if json_data else "")
        if json_data is not None:
            response.json.return_value = json_data
        return response

    return _make_response


# ============================================================================
# Cache data fixtures
# ============================================================================


@pytest.fixture
def cache_entry_valid():
    """Create a valid (not expired) cache entry."""
    import time

    return {"timestamp": time.time(), "value": {"test": "data"}}


@pytest.fixture
def cache_entry_expired():
    """Create an expired cache entry."""
    import time

    return {"timestamp": time.time() - 100000, "value": {"test": "old_data"}}


# ============================================================================
# Logger fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset the global logger state before each test."""
    import woolly.debug as debug_module

    debug_module._logger = None
    debug_module._log_file = None
    debug_module._debug_enabled = False
    yield
    # Clean up after test
    debug_module._logger = None
    debug_module._log_file = None
    debug_module._debug_enabled = False


# ============================================================================
# CLI testing fixtures
# ============================================================================


@pytest.fixture
def cli_runner():
    """Create a fixture for running CLI commands."""
    import subprocess
    import sys

    def run_woolly(*args, check=True, capture_output=True, text=True):
        """Run woolly CLI command with given arguments."""
        cmd = [sys.executable, "-m", "woolly"] + list(args)
        result = subprocess.run(
            cmd, capture_output=capture_output, text=text, check=False
        )
        return result

    return run_woolly

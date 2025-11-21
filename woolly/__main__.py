import argparse
import sys
from typing import Optional
import requests
import subprocess
import re
import json
import hashlib
import time
from pathlib import Path
from rich.tree import Tree
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TaskID
from rich import box
from rich.table import Table

CRATES_API = "https://crates.io/api/v1/crates"
CACHE_DIR = Path.home() / ".cache" / "fedora-rust-checker"
CACHE_TTL = 86400 * 7  # 7 days for crates.io data
FEDORA_CACHE_TTL = 86400  # 1 day for Fedora repoquery data

console = Console()

# Required headers for crates.io API
HEADERS = {"User-Agent": "fedora-rust-checker@0.1.0"}


# ------------------------------------------------------------
# Disk Cache Helpers
# ------------------------------------------------------------
def ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "crates").mkdir(exist_ok=True)
    (CACHE_DIR / "fedora").mkdir(exist_ok=True)


def get_cache_path(namespace: str, key: str) -> Path:
    """Get path for a cache entry."""
    safe_key = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / namespace / f"{safe_key}.json"


def read_cache(namespace: str, key: str, ttl: int = CACHE_TTL):
    """Read from disk cache if not expired."""
    path = get_cache_path(namespace, key)
    if not path.exists():
        return None
    
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("timestamp", 0) > ttl:
            return None  # Expired
        return data.get("value")
    except (json.JSONDecodeError, KeyError):
        return None


def write_cache(namespace: str, key: str, value):
    """Write to disk cache."""
    ensure_cache_dir()
    path = get_cache_path(namespace, key)
    data = {"timestamp": time.time(), "value": value}
    path.write_text(json.dumps(data))


# ------------------------------------------------------------
# Fedora repoquery helpers
# ------------------------------------------------------------
def repoquery_crate(crate: str):
    """
    Query Fedora for a crate using the virtual provides format: crate(name)
    Returns (is_packaged, versions_list, package_names)
    """
    cache_key = f"repoquery:{crate}"
    cached = read_cache("fedora", cache_key, FEDORA_CACHE_TTL)
    if cached is not None:
        return tuple(cached)
    
    provide_pattern = f"crate({crate})"
    
    try:
        out = subprocess.check_output(
            ["dnf", "repoquery", "--whatprovides", provide_pattern,
             "--queryformat", "%{NAME}|%{VERSION}"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        
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
    except subprocess.CalledProcessError:
        result = (False, [], [])
        write_cache("fedora", cache_key, list(result))
        return result


def get_crate_provides_version(crate: str):
    """
    Get the actual crate version provided by Fedora packages.
    """
    cache_key = f"provides:{crate}"
    cached = read_cache("fedora", cache_key, FEDORA_CACHE_TTL)
    if cached is not None:
        return cached
    
    provide_pattern = f"crate({crate})"
    
    try:
        out = subprocess.check_output(
            ["dnf", "repoquery", "--provides", "--whatprovides", provide_pattern],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        
        if not out:
            write_cache("fedora", cache_key, [])
            return []
        
        versions = set()
        pattern = re.compile(rf"crate\({re.escape(crate)}\)\s*=\s*([\d.]+)")
        for line in out.split("\n"):
            match = pattern.search(line)
            if match:
                versions.add(match.group(1))
        
        result = sorted(versions)
        write_cache("fedora", cache_key, result)
        return result
    except subprocess.CalledProcessError:
        write_cache("fedora", cache_key, [])
        return []


def crate_is_packaged(crate: str):
    """
    Check if a crate is packaged in Fedora.
    Returns (is_packaged, crate_versions, package_names)
    """
    is_packaged, pkg_versions, packages = repoquery_crate(crate)
    
    if not is_packaged:
        alt_name = crate.replace("-", "_")
        if alt_name != crate:
            is_packaged, pkg_versions, packages = repoquery_crate(alt_name)
        
        if not is_packaged:
            alt_name = crate.replace("_", "-")
            if alt_name != crate:
                is_packaged, pkg_versions, packages = repoquery_crate(alt_name)
    
    if is_packaged:
        crate_versions = get_crate_provides_version(crate)
        if not crate_versions:
            crate_versions = pkg_versions
        return (True, crate_versions, packages)
    
    return (False, [], [])


# ------------------------------------------------------------
# Crates.io API helpers
# ------------------------------------------------------------
def fetch_crate_info(crate_name: str):
    """Fetch basic crate info (latest version, etc.)"""
    cache_key = f"info:{crate_name}"
    cached = read_cache("crates", cache_key)
    if cached is not None:
        return cached
    
    url = f"{CRATES_API}/{crate_name}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 404:
        write_cache("crates", cache_key, None)
        return None
    if r.status_code != 200:
        raise RuntimeError(f"Failed to fetch metadata for crate {crate_name}: {r.status_code}")
    
    data = r.json()
    write_cache("crates", cache_key, data)
    return data


def fetch_dependencies(crate_name: str, version: str):
    """
    Fetch dependencies for a specific crate version.
    """
    cache_key = f"deps:{crate_name}:{version}"
    cached = read_cache("crates", cache_key)
    if cached is not None:
        return cached
    
    url = f"{CRATES_API}/{crate_name}/{version}/dependencies"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        write_cache("crates", cache_key, [])
        return []
    
    data = r.json()
    deps = data.get("dependencies", [])
    write_cache("crates", cache_key, deps)
    return deps


def get_latest_version(crate_name: str):
    """Get the latest (newest) version of a crate."""
    info = fetch_crate_info(crate_name)
    if info is None:
        return None
    return info["crate"]["newest_version"]


def get_normal_dependencies(crate_name: str, version: Optional[str] = None):
    """
    Returns normal (non-dev, non-build) dependencies as list of tuples:
       [("dep_name", "version_req"), ...]
    """
    if version is None:
        version = get_latest_version(crate_name)
        if version is None:
            return []

    deps = fetch_dependencies(crate_name, version)
    result = []
    for d in deps:
        if d.get("kind") == "normal":
            if d.get("optional", False):
                continue
            result.append((d["crate_id"], d["req"]))
    return result


# ------------------------------------------------------------
# Progress Tracker
# ------------------------------------------------------------
class ProgressTracker:
    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("[dim]{task.fields[status]}[/dim]"),
            console=console,
        )
        self.task: TaskID = TaskID(0)
        self.processed = 0
        self.total_discovered = 0

    def start(self):
        self.task = self.progress.add_task(
            "Analyzing dependencies",
            total=None,
            status="starting..."
        )
        self.progress.start()

    def stop(self):
        self.progress.stop()

    def update(self, crate_name: str, discovered: int = 0):
        self.processed += 1
        self.total_discovered += discovered

        if self.total_discovered > 0:
            self.progress.update(
                self.task,
                completed=self.processed,
                total=self.processed + self.total_discovered,
                status=f"checking: {crate_name}"
            )
        else:
            self.progress.update(
                self.task,
                status=f"checking: {crate_name}"
            )

    def finish(self):
        self.progress.update(
            self.task,
            completed=self.processed,
            total=self.processed,
            status="[green]complete![/green]"
        )


# ------------------------------------------------------------
# Tree Builder (FULLY RECURSIVE)
# ------------------------------------------------------------
def build_tree(crate_name: str, version: Optional[str] = None, visited=None, depth=0, max_depth=50, tracker=None):
    if visited is None:
        visited = set()

    if depth > max_depth:
        return f"[dim]{crate_name} (max depth reached)[/dim]"

    if crate_name in visited:
        return f"[dim]{crate_name} (already visited)[/dim]"
    visited.add(crate_name)

    if tracker:
        tracker.update(crate_name)

    if version is None:
        version = get_latest_version(crate_name)
        if version is None:
            return f"[bold red]{crate_name}[/bold red] • [red]not found on crates.io[/red]"

    # Check Fedora packaging status
    is_packaged, fedora_versions, packages = crate_is_packaged(crate_name)

    if is_packaged:
        ver_str = ", ".join(fedora_versions) if fedora_versions else "unknown"
        pkg_str = ", ".join(packages) if packages else ""
        label = (f"[bold]{crate_name}[/bold] [dim]v{version}[/dim] • "
                f"[green]✓ packaged[/green] [dim]({ver_str})[/dim]")
        if pkg_str:
            label += f" [dim cyan][{pkg_str}][/dim cyan]"
    else:
        label = f"[bold]{crate_name}[/bold] [dim]v{version}[/dim] • [red]✗ not packaged[/red]"

    node = Tree(label)

    # ALWAYS recurse into dependencies regardless of packaging status
    deps = get_normal_dependencies(crate_name, version)
    if tracker and deps:
        tracker.update(crate_name, discovered=len(deps))

    for (dep_name, dep_req) in deps:
        child = build_tree(dep_name, None, visited, depth + 1, max_depth, tracker)
        if isinstance(child, str):
            node.add(child)
        else:
            node.add(child)

    return node


# ------------------------------------------------------------
# Summary Collection
# ------------------------------------------------------------
def collect_stats(tree, stats=None):
    """Walk the tree and collect statistics."""
    if stats is None:
        stats = {"total": 0, "packaged": 0, "missing": 0, "missing_list": [], "packaged_list": []}

    def walk(t):
        if isinstance(t, str):
            stats["total"] += 1
            if "not packaged" in t or "not found" in t:
                stats["missing"] += 1
                name = t.split("[/bold]")[0].split("]")[-1] if "[/bold]" in t else t.split()[0]
                stats["missing_list"].append(name)
            elif "packaged" in t:
                stats["packaged"] += 1
            return

        if hasattr(t, "label"):
            label = str(t.label)
            stats["total"] += 1
            if "not packaged" in label or "not found" in label:
                stats["missing"] += 1
                name = label.split("[/bold]")[0].split("[bold]")[-1] if "[bold]" in label else "unknown"
                stats["missing_list"].append(name)
            elif "packaged" in label:
                stats["packaged"] += 1
                name = label.split("[/bold]")[0].split("[bold]")[-1] if "[bold]" in label else "unknown"
                stats["packaged_list"].append(name)

        if hasattr(t, "children"):
            for child in t.children:
                walk(child)

    walk(tree)
    return stats


def print_summary_table(root_crate, tree):
    stats = collect_stats(tree)

    table = Table(title=f"Dependency Summary for '{root_crate}'", box=box.ROUNDED)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total dependencies checked", str(stats["total"]))
    table.add_row("[green]Packaged in Fedora[/green]", str(stats["packaged"]))
    table.add_row("[red]Missing from Fedora[/red]", str(stats["missing"]))

    console.print(table)
    console.print()

    if stats["missing_list"]:
        console.print("[bold]Missing crates that need packaging:[/bold]")
        for name in sorted(set(stats["missing_list"])):
            console.print(f"  • {name}")
        console.print()


def clear_cache(namespace: Optional[str] = None):
    """Clear disk cache."""
    if namespace:
        cache_path = CACHE_DIR / namespace
        if cache_path.exists():
            for f in cache_path.glob("*.json"):
                f.unlink()
            console.print(f"[yellow]Cleared {namespace} cache[/yellow]")
    else:
        for ns in ["crates", "fedora"]:
            cache_path = CACHE_DIR / ns
            if cache_path.exists():
                for f in cache_path.glob("*.json"):
                    f.unlink()
        console.print("[yellow]Cleared all caches[/yellow]")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check if a Rust crate's dependencies are packaged in Fedora"
    )
    parser.add_argument("crate", nargs="?", help="Crate name on crates.io (e.g., ripgrep)")
    parser.add_argument("--version", "-v", help="Specific version to check")
    parser.add_argument("--max-depth", "-d", type=int, default=50, help="Maximum recursion depth")
    parser.add_argument("--no-progress", action="store_true", help="Disable progress bar")
    parser.add_argument("--clear-cache", action="store_true", help="Clear all cached data")
    parser.add_argument("--clear-fedora-cache", action="store_true", help="Clear Fedora repoquery cache")
    args = parser.parse_args()

    if args.clear_cache:
        clear_cache()
        if not args.crate:
            exit(0)

    if args.clear_fedora_cache:
        clear_cache("fedora")
        if not args.crate:
            exit(0)

    if not args.crate:
        parser.print_help()
        exit(1)

    console.print(f"\n[bold underline]Analyzing crate:[/] {args.crate}")
    console.print(f"[dim]Cache directory: {CACHE_DIR}[/dim]\n")

    tracker = None if args.no_progress else ProgressTracker()

    if tracker:
        tracker.start()

    try:
        tree = build_tree(args.crate, args.version, max_depth=args.max_depth, tracker=tracker)
        if tracker:
            tracker.finish()
    finally:
        if tracker:
            tracker.stop()

    console.print()
    print_summary_table(args.crate, tree)

    console.print("[bold]Dependency Tree:[/bold]")
    console.print(tree)
    console.print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
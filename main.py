#!/usr/bin/env python3
import requests
import subprocess
from functools import lru_cache
from rich.tree import Tree
from rich.console import Console
from rich import box
from rich.table import Table

CRATES_API = "https://crates.io/api/v1/crates"
console = Console()


# ------------------------------------------------------------
# Fedora repoquery helpers
# ------------------------------------------------------------
def repoquery_versions(crate: str):
    """
    Returns a list of versions available in Fedora for `rust-<crate>`.
    """
    pattern = f"rust-{crate}"
    try:
        out = subprocess.check_output(
            ["repoquery", "--queryformat", "%{VERSION}", "--whatprovides", pattern],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        versions = [v for v in out.split("\n") if v]
        return versions
    except subprocess.CalledProcessError:
        return []


def check_packaging_status(crate: str, required_version: str = None):
    """
    Determine whether Fedora has:
      - the dependency fully packaged (correct version)
      - the crate but with a different version
      - or not at all
    """
    versions = repoquery_versions(crate)

    if not versions:
        return {
            "status": "not_found",
            "available": [],
            "required": required_version,
        }

    if required_version and required_version not in versions:
        return {
            "status": "missing_version",
            "available": versions,
            "required": required_version,
        }

    return {
        "status": "packaged",
        "available": versions,
        "required": required_version,
    }


# ------------------------------------------------------------
# Crates.io dependencies
# ------------------------------------------------------------
@lru_cache
def fetch_crate_metadata(crate_name: str, version: str = None):
    url = f"{CRATES_API}/{crate_name}"
    if version:
        url += f"/{version}"
    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to fetch metadata for crate {crate_name}")
    return r.json()


def get_dependencies_with_versions(crate_name: str, version: str = None):
    """
    Returns dependencies WITH version requirements:
       [("url", "2.5.0"), ("serde", "1.0"), ...]
    """
    data = fetch_crate_metadata(crate_name, version)

    if not version:
        version = data["crate"]["newest_version"]

    for v in data.get("versions", []):
        if v["num"] == version:
            deps = v.get("dependencies", [])
            result = []
            for d in deps:
                if d["kind"] == "normal":
                    # Simple version extraction: use exact version if available
                    req = d["req"].lstrip("^>=< ")
                    result.append((d["crate_id"], req))
            return result

    return []


# ------------------------------------------------------------
# Tree Builder
# ------------------------------------------------------------
def build_tree(crate_name: str, version: str = None, visited=None):
    if visited is None:
        visited = set()

    if crate_name in visited:
        return f"[yellow]{crate_name} (already visited)[/yellow]"
    visited.add(crate_name)

    deps = get_dependencies_with_versions(crate_name, version)
    crate_version = fetch_crate_metadata(crate_name)["crate"]["newest_version"]

    status = check_packaging_status(crate_name, crate_version)

    # Display rules
    if status["status"] == "packaged":
        label = f"[bold]{crate_name}[/bold] • [green]packaged[/] ({crate_version})"
    elif status["status"] == "missing_version":
        label = (
            f"[bold]{crate_name}[/bold] • [yellow]missing_version[/] "
            f"(needed: {crate_version}, available: {', '.join(status['available'])})"
        )
    else:
        label = f"[bold]{crate_name}[/bold] • [red]not_found[/]"

    node = Tree(label)

    # If fully packaged, stop recursion
    if status["status"] == "packaged":
        return node

    # Recurse into dependencies
    for (dep, dep_ver) in deps:
        child = build_tree(dep, dep_ver, visited)
        node.add(child)

    return node


# ------------------------------------------------------------
# Summary Table
# ------------------------------------------------------------
def print_summary_table(root_crate, tree):
    all_nodes = []
    missing = []
    missing_version = []

    def walk(t):
        for child in t.children:
            label = child.label if hasattr(child, "label") else child
            all_nodes.append(label)
            if "not_found" in label:
                missing.append(label)
            if "missing_version" in label:
                missing_version.append(label)
            if isinstance(child, Tree):
                walk(child)

    walk(tree)

    table = Table(title=f"Dependency Summary for '{root_crate}'", box=box.SIMPLE_HEAVY)
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Total dependencies (recursive)", str(len(all_nodes)))
    table.add_row("Missing completely", str(len(missing)))
    table.add_row("Missing required version", str(len(missing_version)))

    console.print(table)
    console.print()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fedora Rust dependency checker (Rich UI)")
    parser.add_argument("crate", help="Crate name on crates.io (e.g., oauth2)")
    parser.add_argument("--version", help="Specific version to check")
    args = parser.parse_args()

    console.print(f"\n[bold underline]Analyzing crate:[/] {args.crate}\n")

    tree = build_tree(args.crate, args.version)

    print_summary_table(args.crate, tree)

    console.print(tree)
    console.print()


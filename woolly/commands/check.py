"""
Check command - analyze package dependencies for Fedora availability.
"""

import fnmatch
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated, Optional

import cyclopts
from pydantic import BaseModel, Field
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from woolly.cache import CACHE_DIR
from woolly.commands import app, console
from woolly.debug import get_log_file, log, log_package_check, setup_logger
from woolly.languages import get_available_languages, get_provider
from woolly.languages.base import Dependency, FeatureInfo, LanguageProvider
from woolly.progress import ProgressTracker
from woolly.reporters import ReportData, get_available_formats, get_reporter


class DevBuildDepStatus(BaseModel):
    """Status of a dev or build dependency."""

    name: str
    version_requirement: str
    is_packaged: bool
    fedora_versions: list[str] = Field(default_factory=list)
    fedora_packages: list[str] = Field(default_factory=list)


class TreeStats(BaseModel):
    """Statistics collected from dependency tree analysis."""

    total: int = 0
    packaged: int = 0
    missing: int = 0
    missing_list: list[str] = Field(default_factory=list)
    packaged_list: list[str] = Field(default_factory=list)
    optional_total: int = 0
    optional_packaged: int = 0
    optional_missing: int = 0
    optional_missing_list: list[str] = Field(default_factory=list)
    dev_total: int = 0
    dev_packaged: int = 0
    dev_missing: int = 0
    build_total: int = 0
    build_packaged: int = 0
    build_missing: int = 0


def _compute_stats_from_visited(visited: dict) -> TreeStats:
    """Compute statistics directly from the *visited* dict built during tree traversal.

    This replaces the old ``collect_stats`` approach that parsed Rich
    markup strings, which was fragile and wasteful.  The *visited* dict
    already contains all the structured information we need:
    ``{package_name: (is_packaged, version, is_optional)}``.
    """
    stats = TreeStats()
    for pkg_name, (is_packaged, _version, is_optional) in visited.items():
        stats.total += 1
        if is_optional:
            stats.optional_total += 1
        if is_packaged:
            stats.packaged += 1
            stats.packaged_list.append(pkg_name)
            if is_optional:
                stats.optional_packaged += 1
        else:
            stats.missing += 1
            stats.missing_list.append(pkg_name)
            if is_optional:
                stats.optional_missing += 1
                stats.optional_missing_list.append(pkg_name)
    return stats


def build_tree(
    provider: LanguageProvider,
    package_name: str,
    version: Optional[str] = None,
    visited: Optional[dict] = None,
    depth: int = 0,
    max_depth: int = 50,
    tracker: Optional[ProgressTracker] = None,
    include_optional: bool = False,
    is_optional_dep: bool = False,
    exclude_patterns: Optional[list[str]] = None,
):
    """
    Recursively build a dependency tree for a package.

    Parameters
    ----------
    provider
        The language provider to use.
    package_name
        Name of the package to analyze.
    version
        Specific version, or None for latest.
    visited
        Dict of already-visited packages mapping to their status.
        Each value is a tuple ``(is_packaged, version, is_optional)``.
    depth
        Current recursion depth.
    max_depth
        Maximum recursion depth.
    tracker
        Optional progress tracker.
    include_optional
        If True, include optional dependencies in the analysis.
    is_optional_dep
        If True, this package is an optional dependency.
    exclude_patterns
        List of glob patterns to exclude from the dependency tree.

    Returns
    -------
    Tree
        Rich Tree object representing the dependency tree.
    """
    if visited is None:
        visited = {}

    optional_marker = " [yellow](optional)[/yellow]" if is_optional_dep else ""

    if depth > max_depth:
        log(f"Max depth reached for {package_name}", level="warning", depth=depth)
        return f"[dim]{package_name}{optional_marker} (max depth reached)[/dim]"

    if package_name in visited:
        is_packaged, cached_version, _ = visited[package_name]
        log_package_check(
            package_name,
            "Skip (already visited)",
            result="packaged" if is_packaged else "not packaged",
        )
        if is_packaged:
            return f"[dim]{package_name}[/dim] [dim]v{cached_version}[/dim]{optional_marker} • [green]✓[/green] [dim](already visited)[/dim]"
        else:
            return f"[dim]{package_name}[/dim]{optional_marker} • [red]✗[/red] [dim](already visited)[/dim]"

    if tracker:
        tracker.update(package_name)

    log_package_check(package_name, "Fetching version", source=provider.registry_name)

    # Fetch full package info to get version and license
    pkg_info = None
    if version is None:
        pkg_info = provider.fetch_package_info(package_name)
        if pkg_info is None:
            visited[package_name] = (False, None, is_optional_dep)
            log_package_check(
                package_name, "Not found", source=provider.registry_name, result="error"
            )
            return (
                f"[bold red]{package_name}[/bold red]{optional_marker} • "
                f"[red]not found on {provider.registry_name}[/red]"
            )
        version = pkg_info.latest_version
    else:
        pkg_info = provider.fetch_package_info(package_name)

    license_str = ""
    if pkg_info and pkg_info.license:
        license_str = f" [magenta]({pkg_info.license})[/magenta]"

    log_package_check(package_name, "Checking Fedora", source="dnf repoquery")

    # Check Fedora packaging status
    status = provider.check_fedora_packaging(package_name)
    visited[package_name] = (status.is_packaged, version, is_optional_dep)

    if status.is_packaged:
        log_package_check(
            package_name,
            "Fedora status",
            result=f"packaged ({', '.join(status.versions)})",
        )
    else:
        log_package_check(package_name, "Fedora status", result="not packaged")

    if status.is_packaged:
        ver_str = ", ".join(status.versions) if status.versions else "unknown"
        pkg_str = ", ".join(status.package_names) if status.package_names else ""
        label = (
            f"[bold]{package_name}[/bold] [dim]v{version}[/dim]{license_str}{optional_marker} • "
            f"[green]✓ packaged[/green] [dim]({ver_str})[/dim]"
        )
        if pkg_str:
            label += f" [dim cyan][{pkg_str}][/dim cyan]"
    else:
        label = (
            f"[bold]{package_name}[/bold] [dim]v{version}[/dim]{license_str}{optional_marker} • "
            f"[red]✗ not packaged[/red]"
        )

    node = Tree(label)

    # ALWAYS recurse into dependencies regardless of packaging status
    log_package_check(
        package_name, "Fetching dependencies", source=provider.registry_name
    )

    deps = provider.get_normal_dependencies(
        package_name, version, include_optional=include_optional
    )

    log(f"Found {len(deps)} dependencies for {package_name}", deps=len(deps))

    if tracker and deps:
        tracker.update(package_name, discovered=len(deps))

    for dep_name, _dep_req, dep_is_optional in deps:
        # Skip dependencies matching exclude patterns
        if exclude_patterns:
            if any(fnmatch.fnmatch(dep_name, pattern) for pattern in exclude_patterns):
                log(f"Filtered out dependency: {dep_name}", level="info", depth=depth)
                continue

        child = build_tree(
            provider,
            dep_name,
            None,
            visited,
            depth + 1,
            max_depth,
            tracker,
            include_optional=include_optional,
            is_optional_dep=dep_is_optional,
            exclude_patterns=exclude_patterns,
        )
        if isinstance(child, str):
            node.add(child)
        elif isinstance(child, Tree):
            # Directly append Tree children to avoid wrapping
            # Rich's add() would wrap the Tree in another node
            node.children.append(child)
        else:
            node.add(child)

    return node


def _check_fedora_for_dep(
    provider: LanguageProvider, dep: Dependency
) -> DevBuildDepStatus:
    """Check Fedora packaging status for a single dev/build dependency.

    This is extracted as a standalone function so it can be submitted to
    a :class:`~concurrent.futures.ThreadPoolExecutor`.
    """
    fedora_status = provider.check_fedora_packaging(dep.name)
    return DevBuildDepStatus(
        name=dep.name,
        version_requirement=dep.version_requirement,
        is_packaged=fedora_status.is_packaged,
        fedora_versions=fedora_status.versions,
        fedora_packages=fedora_status.package_names,
    )


@app.command(name="check")
def check(
    package: Annotated[
        str,
        cyclopts.Parameter(
            help="Package name to check.",
        ),
    ],
    *,
    lang: Annotated[
        str,
        cyclopts.Parameter(
            ("--lang", "-l"),
            help="Language/ecosystem. Use 'list-languages' to see options.",
        ),
    ] = "rust",
    version: Annotated[
        Optional[str],
        cyclopts.Parameter(
            ("--version", "-v"),
            help="Specific version to check.",
        ),
    ] = None,
    max_depth: Annotated[
        int,
        cyclopts.Parameter(
            ("--max-depth", "-d"),
            help="Maximum recursion depth.",
        ),
    ] = 50,
    optional: Annotated[
        bool,
        cyclopts.Parameter(
            ("--optional", "-o"),
            negative=(),
            help="Include optional dependencies in the analysis.",
        ),
    ] = False,
    no_progress: Annotated[
        bool,
        cyclopts.Parameter(
            negative=(),
            help="Disable progress bar.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        cyclopts.Parameter(
            negative=(),
            help="Enable verbose debug logging (includes command outputs and API responses).",
        ),
    ] = False,
    report: Annotated[
        str,
        cyclopts.Parameter(
            ("--report", "-r"),
            help="Report format: stdout, json, markdown. Use 'list-formats' for all options.",
        ),
    ] = "stdout",
    missing_only: Annotated[
        bool,
        cyclopts.Parameter(
            ("--missing-only", "-m"),
            negative=(),
            help="Only display packages that are missing from Fedora.",
        ),
    ] = False,
    exclude: Annotated[
        tuple[str, ...],
        cyclopts.Parameter(
            ("--exclude", "-e"),
            help="Glob pattern(s) to exclude dependencies (e.g., '*-windows', 'win*'). Can be specified multiple times.",
        ),
    ] = (),
    template: Annotated[
        Optional[str],
        cyclopts.Parameter(
            ("--template", "-t"),
            help="Path to a Jinja2 template file for custom report format. Only used with --report=template.",
        ),
    ] = None,
    release: Annotated[
        Optional[str],
        cyclopts.Parameter(
            ("--release", "-R"),
            help="Fedora release version to check against (e.g., '41', '42', 'rawhide').",
        ),
    ] = None,
    repos: Annotated[
        tuple[str, ...],
        cyclopts.Parameter(
            ("--repos",),
            help="Fedora repo(s) to query (e.g., 'fedora', 'updates', 'updates-testing'). Can be specified multiple times.",
        ),
    ] = (),
):
    """Check if a package's dependencies are available in Fedora.

    Parameters
    ----------
    package
        The name of the package to analyze.
    lang
        Language/ecosystem (default: rust).
    version
        Specific version to check (default: latest).
    max_depth
        Maximum recursion depth for dependency tree.
    optional
        Include optional dependencies in the analysis.
    no_progress
        Disable progress bar during analysis.
    debug
        Enable verbose debug logging.
    report
        Output format for the report.
    missing_only
        Only display packages that are missing from Fedora.
    exclude
        Glob pattern(s) to exclude dependencies from the analysis.
    template
        Path to a Jinja2 template file for custom report format.
    release
        Fedora release version to check against (e.g., '41', 'rawhide').
    repos
        Fedora repo(s) to query (e.g., 'fedora', 'updates', 'updates-testing').
    """
    # Get the language provider
    provider = get_provider(lang)
    if provider is None:
        console.print(f"[red]Unknown language: {lang}[/red]")
        console.print(f"Available languages: {', '.join(get_available_languages())}")
        raise SystemExit(1)

    # Get the reporter
    template_path = Path(template) if template else None

    # Validate template reporter requirements
    if report.lower() in ("template", "tpl", "jinja", "jinja2"):
        if template_path is None:
            console.print("[red]Template reporter requires --template parameter.[/red]")
            console.print(
                "Example: woolly check mypackage --report=template --template=my_template.md"
            )
            raise SystemExit(1)
        if not template_path.exists():
            console.print(f"[red]Template file not found: {template_path}[/red]")
            raise SystemExit(1)
    elif template_path is not None:
        console.print(
            "[yellow]Warning: --template is only used with --report=template[/yellow]"
        )

    reporter = get_reporter(report, console=console, template_path=template_path)
    if reporter is None:
        console.print(f"[red]Unknown report format: {report}[/red]")
        console.print(f"Available formats: {', '.join(get_available_formats())}")
        raise SystemExit(1)

    # Convert exclude tuple to list for consistency
    exclude_patterns = list(exclude) if exclude else None

    # Configure Fedora release / repo targeting on the provider
    fedora_repos_list = list(repos) if repos else None
    if release:
        provider.fedora_release = release
    if fedora_repos_list:
        provider.fedora_repos = fedora_repos_list

    # Initialize logging
    setup_logger(debug=debug)
    log(
        "Analysis started",
        package=package,
        language=lang,
        max_depth=max_depth,
        include_optional=optional,
        debug=debug,
        report_format=report,
        exclude_patterns=exclude_patterns,
        fedora_release=release,
        fedora_repos=fedora_repos_list,
    )

    # ── Fetch root package info once (reused for license, version,
    #    features, and dev/build deps – avoids redundant calls) ──
    root_info = provider.fetch_package_info(package)
    root_license = root_info.license if root_info else None
    resolved_version = version or (root_info.latest_version if root_info else None)

    header = Text()
    header.append(package, style="bold cyan")
    header.append(f" ({provider.display_name})\n", style="dim")
    header.append(f"Registry:  {provider.registry_name}\n", style="dim")
    header.append(f"Cache:     {CACHE_DIR}", style="dim")
    if release:
        header.append("\n")
        header.append(f"Release:   {release}", style="dim")
    if fedora_repos_list:
        header.append("\n")
        header.append(f"Repos:     {', '.join(fedora_repos_list)}", style="dim")
    if optional:
        header.append("\n")
        header.append("Including optional dependencies", style="yellow")
    if exclude_patterns:
        header.append("\n")
        header.append(
            f"Excluding dependencies matching: {', '.join(exclude_patterns)}",
            style="yellow",
        )

    console.print()
    console.print(
        Panel(
            header,
            title="[bold]Analyzing Dependencies[/bold]",
            border_style="blue",
            padding=(0, 1),
        )
    )

    tracker = None if no_progress else ProgressTracker(console)

    if tracker:
        tracker.start(f"Analyzing {provider.display_name} dependencies")

    # Shared visited dict – build_tree populates it, then we derive stats.
    visited: dict[str, tuple[bool, Optional[str], bool]] = {}

    try:
        tree = build_tree(
            provider,
            package,
            version,
            visited=visited,
            max_depth=max_depth,
            tracker=tracker,
            include_optional=optional,
            exclude_patterns=exclude_patterns,
        )
        if tracker:
            tracker.finish()
    finally:
        if tracker:
            tracker.stop()
        log("Analysis complete")

    console.print()

    # ── Collect statistics directly from the visited dict ──
    stats = _compute_stats_from_visited(visited)

    # Fetch features/extras for the root package
    features: list[FeatureInfo] = []
    if resolved_version:
        features = provider.fetch_features(package, resolved_version)

    # ── Fetch dev and build deps in one call, check Fedora in parallel ──
    dev_deps_status: list[DevBuildDepStatus] = []
    build_deps_status: list[DevBuildDepStatus] = []

    if resolved_version:
        # Single fetch_dependencies call partitioned by kind
        _normal, dev_deps, build_deps = provider.get_all_dependencies(
            package, resolved_version, include_optional=optional
        )

        all_devbuild: list[Dependency] = dev_deps + build_deps
        if all_devbuild:
            # Check Fedora status for dev/build deps in parallel
            results: dict[str, DevBuildDepStatus] = {}
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_dep = {
                    executor.submit(_check_fedora_for_dep, provider, dep): dep
                    for dep in all_devbuild
                }
                for future in as_completed(future_to_dep):
                    dep = future_to_dep[future]
                    results[dep.name] = future.result()

            # Preserve original ordering
            for dep in dev_deps:
                dev_deps_status.append(results[dep.name])
            for dep in build_deps:
                build_deps_status.append(results[dep.name])

    stats.dev_total = len(dev_deps_status)
    stats.dev_packaged = sum(1 for d in dev_deps_status if d.is_packaged)
    stats.dev_missing = sum(1 for d in dev_deps_status if not d.is_packaged)
    stats.build_total = len(build_deps_status)
    stats.build_packaged = sum(1 for d in build_deps_status if d.is_packaged)
    stats.build_missing = sum(1 for d in build_deps_status if not d.is_packaged)

    # Create report data
    report_data = ReportData(
        root_package=package,
        language=provider.display_name,
        registry=provider.registry_name,
        total_dependencies=stats.total,
        packaged_count=stats.packaged,
        missing_count=stats.missing,
        missing_packages=stats.missing_list,
        packaged_packages=stats.packaged_list,
        tree=tree,
        max_depth=max_depth,
        version=version,
        include_optional=optional,
        optional_total=stats.optional_total,
        optional_packaged=stats.optional_packaged,
        optional_missing=stats.optional_missing,
        optional_missing_packages=stats.optional_missing_list,
        missing_only=missing_only,
        root_license=root_license,
        features=features,
        dev_dependencies=[d.model_dump() for d in dev_deps_status],
        build_dependencies=[d.model_dump() for d in build_deps_status],
        dev_total=stats.dev_total,
        dev_packaged=stats.dev_packaged,
        dev_missing=stats.dev_missing,
        build_total=stats.build_total,
        build_packaged=stats.build_packaged,
        build_missing=stats.build_missing,
        fedora_release=release,
        fedora_repos=fedora_repos_list,
    )

    # Generate report
    if reporter.writes_to_file:
        output_path = reporter.write_report(report_data)
        console.print(f"[green]Report saved to: {output_path}[/green]")
    else:
        reporter.generate(report_data)

    # Show log file path
    log_file = get_log_file()
    if log_file:
        console.print(f"[dim]Log saved to: {log_file}[/dim]\n")

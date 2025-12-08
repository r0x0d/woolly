"""
Check command - analyze package dependencies for Fedora availability.
"""

import fnmatch
from pathlib import Path
from typing import Annotated, Optional

import cyclopts
from pydantic import BaseModel, Field
from rich.tree import Tree

from woolly.cache import CACHE_DIR
from woolly.commands import app, console
from woolly.debug import get_log_file, log, log_package_check, setup_logger
from woolly.languages import get_available_languages, get_provider
from woolly.languages.base import LanguageProvider
from woolly.progress import ProgressTracker
from woolly.reporters import ReportData, get_available_formats, get_reporter


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
        is_packaged, cached_version = visited[package_name]
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

    if version is None:
        version = provider.get_latest_version(package_name)
        if version is None:
            visited[package_name] = (False, None)
            log_package_check(
                package_name, "Not found", source=provider.registry_name, result="error"
            )
            return (
                f"[bold red]{package_name}[/bold red]{optional_marker} • "
                f"[red]not found on {provider.registry_name}[/red]"
            )

    log_package_check(package_name, "Checking Fedora", source="dnf repoquery")

    # Check Fedora packaging status
    status = provider.check_fedora_packaging(package_name)
    visited[package_name] = (status.is_packaged, version)

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
            f"[bold]{package_name}[/bold] [dim]v{version}[/dim]{optional_marker} • "
            f"[green]✓ packaged[/green] [dim]({ver_str})[/dim]"
        )
        if pkg_str:
            label += f" [dim cyan][{pkg_str}][/dim cyan]"
    else:
        label = (
            f"[bold]{package_name}[/bold] [dim]v{version}[/dim]{optional_marker} • "
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


def collect_stats(tree, stats: Optional[TreeStats] = None) -> TreeStats:
    """Walk the tree and collect statistics."""
    if stats is None:
        stats = TreeStats()

    def walk(t):
        if isinstance(t, str):
            stats.total += 1
            is_optional = "(optional)" in t
            if is_optional:
                stats.optional_total += 1
            if "not packaged" in t or "not found" in t:
                stats.missing += 1
                # Handle both [bold] and [bold red] formats
                if "[/bold]" in t:
                    name = t.split("[/bold]")[0].split("]")[-1]
                elif "[/bold red]" in t:
                    name = t.split("[/bold red]")[0].split("[bold red]")[-1]
                else:
                    name = t.split()[0]
                stats.missing_list.append(name)
                if is_optional:
                    stats.optional_missing += 1
                    stats.optional_missing_list.append(name)
            elif "packaged" in t:
                stats.packaged += 1
                if is_optional:
                    stats.optional_packaged += 1
            return

        if hasattr(t, "label"):
            label = str(t.label)
            stats.total += 1
            is_optional = "(optional)" in label
            if is_optional:
                stats.optional_total += 1
            if "not packaged" in label or "not found" in label:
                stats.missing += 1
                # Handle both [bold] and [bold red] formats
                if "[bold]" in label and "[bold red]" not in label:
                    name = label.split("[/bold]")[0].split("[bold]")[-1]
                elif "[bold red]" in label:
                    name = label.split("[/bold red]")[0].split("[bold red]")[-1]
                else:
                    name = "unknown"
                stats.missing_list.append(name)
                if is_optional:
                    stats.optional_missing += 1
                    stats.optional_missing_list.append(name)
            elif "packaged" in label:
                stats.packaged += 1
                name = (
                    label.split("[/bold]")[0].split("[bold]")[-1]
                    if "[bold]" in label
                    else "unknown"
                )
                stats.packaged_list.append(name)
                if is_optional:
                    stats.optional_packaged += 1

        if hasattr(t, "children"):
            for child in t.children:
                walk(child)

    walk(tree)
    return stats


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
    )

    console.print(
        f"\n[bold underline]Analyzing {provider.display_name} package:[/] {package}"
    )
    if optional:
        console.print("[yellow]Including optional dependencies[/yellow]")
    if exclude_patterns:
        console.print(
            f"[yellow]Excluding dependencies matching: {', '.join(exclude_patterns)}[/yellow]"
        )
    console.print(f"[dim]Registry: {provider.registry_name}[/dim]")
    console.print(f"[dim]Cache directory: {CACHE_DIR}[/dim]")
    console.print()

    tracker = None if no_progress else ProgressTracker(console)

    if tracker:
        tracker.start(f"Analyzing {provider.display_name} dependencies")

    try:
        tree = build_tree(
            provider,
            package,
            version,
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

    # Collect statistics
    stats = collect_stats(tree)

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

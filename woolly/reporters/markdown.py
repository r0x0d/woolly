"""
Markdown report generator.

Generates a markdown file with the full dependency analysis.
"""

from woolly.reporters.base import ReportData, Reporter, strip_markup


class MarkdownReporter(Reporter):
    """Reporter that generates a Markdown file."""

    name = "markdown"
    description = "Markdown report file"
    file_extension = "md"
    writes_to_file = True

    def generate(self, data: ReportData) -> str:
        """Generate markdown report content."""
        lines = []

        # Header
        lines.append(f"# Dependency Report: {data.root_package}")
        lines.append("")
        lines.append(f"**Generated:** {data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Language:** {data.language}")
        lines.append(f"**Registry:** {data.registry}")
        if data.version:
            lines.append(f"**Version:** {data.version}")
        if data.include_optional:
            lines.append("**Include optional:** Yes")
        if data.missing_only:
            lines.append("**Missing only:** Yes")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total dependencies checked | {data.total_dependencies} |")
        lines.append(f"| Packaged in Fedora | {data.packaged_count} |")
        lines.append(f"| Missing from Fedora | {data.missing_count} |")

        # Optional dependency stats
        if data.optional_total > 0:
            lines.append(f"| Optional dependencies | {data.optional_total} |")
            lines.append(f"| Optional - Packaged | {data.optional_packaged} |")
            lines.append(f"| Optional - Missing | {data.optional_missing} |")
        lines.append("")

        # Missing packages - use computed properties from ReportData
        required_missing = data.required_missing_packages
        optional_missing = data.optional_missing_set

        if required_missing:
            lines.append("## Missing Packages")
            lines.append("")
            lines.append("The following packages need to be packaged for Fedora:")
            lines.append("")
            for name in sorted(required_missing):
                lines.append(f"- `{name}`")
            lines.append("")

        if optional_missing:
            lines.append("## Missing Optional Packages")
            lines.append("")
            lines.append("The following optional packages are not available in Fedora:")
            lines.append("")
            for name in sorted(optional_missing):
                lines.append(f"- `{name}` *(optional)*")
            lines.append("")

        # Packaged packages - use computed property (skip if missing_only mode)
        if data.unique_packaged_packages and not data.missing_only:
            lines.append("## Packaged Packages")
            lines.append("")
            lines.append("The following packages are already available in Fedora:")
            lines.append("")
            for name in sorted(data.unique_packaged_packages):
                lines.append(f"- `{name}`")
            lines.append("")

        # Dependency tree (skip if missing_only mode)
        if not data.missing_only:
            lines.append("## Dependency Tree")
            lines.append("")
            lines.append("```")
            lines.append(self._tree_to_text(data.tree))
            lines.append("```")
            lines.append("")

        return "\n".join(lines)

    def _tree_to_text(self, tree, prefix: str = "") -> str:
        """Convert Rich Tree to plain text representation."""
        lines = []

        # Get label text (strip Rich markup) using inherited method and shared utility
        label = self._get_label(tree)
        label = strip_markup(label)

        lines.append(label)

        # Get children using inherited method
        children = self._get_children(tree)

        for i, child in enumerate(children):
            is_last_child = i == len(children) - 1
            child_prefix = "└── " if is_last_child else "├── "
            continuation = "    " if is_last_child else "│   "

            child_text = self._tree_to_text(child, prefix + continuation)
            child_lines = child_text.split("\n")
            lines.append(prefix + child_prefix + child_lines[0])
            for line in child_lines[1:]:
                if line:  # Skip empty lines
                    lines.append(line)

        return "\n".join(lines)

"""
Markdown report generator.

Generates a markdown file with the full dependency analysis.
"""

import re

from woolly.reporters.base import Reporter, ReportData


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

        # Missing packages
        required_missing = set(data.missing_packages) - set(
            data.optional_missing_packages
        )
        optional_missing = set(data.optional_missing_packages)

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

        # Packaged packages
        if data.packaged_packages:
            lines.append("## Packaged Packages")
            lines.append("")
            lines.append("The following packages are already available in Fedora:")
            lines.append("")
            for name in sorted(set(data.packaged_packages)):
                lines.append(f"- `{name}`")
            lines.append("")

        # Dependency tree
        lines.append("## Dependency Tree")
        lines.append("")
        lines.append("```")
        lines.append(self._tree_to_text(data.tree))
        lines.append("```")
        lines.append("")

        return "\n".join(lines)

    def _get_label(self, node) -> str:
        """Extract the label text from a tree node, handling nested Trees."""
        # If it's a string, return it directly
        if isinstance(node, str):
            return node

        # Try to get label attribute (Rich Tree has this)
        if hasattr(node, "label"):
            label = node.label
            # If label is None, return empty string
            if label is None:
                return ""
            # If label is another Tree-like object (has its own label), recurse
            if hasattr(label, "label"):
                return self._get_label(label)
            # Otherwise convert to string
            return str(label)

        # Fallback - shouldn't happen
        return str(node)

    def _get_children(self, node) -> list:
        """Get all children from a tree node, flattening nested Trees."""
        children = []

        if hasattr(node, "children"):
            for child in node.children:
                # If the child's label is itself a Tree, use that Tree's children
                if hasattr(child, "label") and hasattr(child.label, "children"):
                    # The child is a wrapper around another tree
                    children.append(child.label)
                else:
                    children.append(child)

        return children

    def _tree_to_text(self, tree, prefix: str = "") -> str:
        """Convert Rich Tree to plain text representation."""
        lines = []

        # Get label text (strip Rich markup)
        label = self._get_label(tree)
        label = self._strip_markup(label)

        lines.append(label)

        # Get children
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

    def _strip_markup(self, text: str) -> str:
        """Strip Rich markup from text."""
        # Remove Rich markup tags like [bold], [/bold], [green], etc.
        return re.sub(r"\[/?[^\]]+\]", "", text)

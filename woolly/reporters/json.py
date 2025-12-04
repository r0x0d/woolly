"""
JSON report generator.

Generates a JSON file with structured data for machine consumption.
"""

import re
import json
from typing import Any

from woolly.reporters.base import Reporter, ReportData


class JsonReporter(Reporter):
    """Reporter that generates a JSON file."""

    name = "json"
    description = "JSON report file (machine-readable)"
    file_extension = "json"
    writes_to_file = True

    def generate(self, data: ReportData) -> str:
        """Generate JSON report content."""
        report = {
            "metadata": {
                "generated_at": data.timestamp.isoformat(),
                "tool": "woolly",
                "root_package": data.root_package,
                "language": data.language,
                "registry": data.registry,
                "version": data.version,
                "max_depth": data.max_depth,
                "include_optional": data.include_optional,
            },
            "summary": {
                "total_dependencies": data.total_dependencies,
                "packaged_count": data.packaged_count,
                "missing_count": data.missing_count,
                "optional": {
                    "total": data.optional_total,
                    "packaged": data.optional_packaged,
                    "missing": data.optional_missing,
                },
            },
            "missing_packages": sorted(
                set(data.missing_packages) - set(data.optional_missing_packages)
            ),
            "missing_optional_packages": sorted(set(data.optional_missing_packages)),
            "packaged_packages": sorted(set(data.packaged_packages)),
            "dependency_tree": self._tree_to_dict(data.tree),
        }

        return json.dumps(report, indent=2)

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

    def _tree_to_dict(self, tree) -> dict[str, Any]:
        """Convert Rich Tree to dictionary representation."""
        label = self._get_label(tree)
        result = self._parse_label(label)

        # Get children
        children = self._get_children(tree)

        if children:
            result["dependencies"] = [self._tree_to_dict(child) for child in children]

        return result

    def _parse_label(self, label: str) -> dict[str, Any]:
        """Parse a tree label into structured data."""
        # Strip Rich markup
        clean_label = re.sub(r"\[/?[^\]]+\]", "", label)

        result: dict[str, Any] = {
            "raw": clean_label.strip(),
        }

        # Check if this is an optional dependency
        result["optional"] = "(optional)" in clean_label

        # Try to extract package name and version
        # Pattern: "package_name vX.Y.Z (optional) • status" or "package_name vX.Y.Z • status"
        match = re.match(
            r"^(\S+)\s*(?:v([\d.]+))?\s*(?:\(optional\))?\s*•\s*(.+)$",
            clean_label.strip(),
        )
        if match:
            result["name"] = match.group(1)
            if match.group(2):
                result["version"] = match.group(2)

            status_text = match.group(3).strip()
            if (
                "packaged" in status_text.lower()
                and "not packaged" not in status_text.lower()
            ):
                result["status"] = "packaged"
                # Try to extract Fedora versions
                ver_match = re.search(r"\(([\d., ]+)\)", status_text)
                if ver_match:
                    result["fedora_versions"] = [
                        v.strip() for v in ver_match.group(1).split(",")
                    ]
                # Try to extract package names
                pkg_match = re.search(r"\[([^\]]+)\]", status_text)
                if pkg_match:
                    result["fedora_packages"] = [
                        p.strip() for p in pkg_match.group(1).split(",")
                    ]
            elif "not packaged" in status_text.lower():
                result["status"] = "not_packaged"
            elif "not found" in status_text.lower():
                result["status"] = "not_found"
            elif "already visited" in status_text.lower():
                result["status"] = "visited"
                result["is_packaged"] = "✓" in status_text
        else:
            # Simpler patterns
            if "already visited" in clean_label:
                result["status"] = "visited"
                result["is_packaged"] = "✓" in clean_label
            elif "max depth" in clean_label:
                result["status"] = "max_depth_reached"

        return result

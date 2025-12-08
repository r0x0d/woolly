"""
Base abstract class defining the contract for report generators.

To add support for a new report format, create a new module in the `reporters/` directory
that implements a class inheriting from `Reporter`. The class must implement
all abstract methods defined here.

Example:
    class HtmlReporter(Reporter):
        name = "html"
        description = "HTML report with interactive tree"
        file_extension = "html"

        def generate(self, data: ReportData) -> str:
            # Generate HTML content
            ...
"""

import re
from abc import ABC, abstractmethod
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


def strip_markup(text: str) -> str:
    """
    Strip Rich markup from text.

    Removes Rich markup tags like [bold], [/bold], [green], etc.

    Args:
        text: Text containing Rich markup.

    Returns:
        Plain text without markup.
    """
    return re.sub(r"\[/?[^\]]+\]", "", text)


class ReportData(BaseModel):
    """All data needed to generate a report."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Package info
    root_package: str
    language: str
    registry: str

    # Statistics
    total_dependencies: int
    packaged_count: int
    missing_count: int
    missing_packages: list[str] = Field(default_factory=list)
    packaged_packages: list[str] = Field(default_factory=list)

    # Optional dependency statistics
    include_optional: bool = False
    optional_total: int = 0
    optional_packaged: int = 0
    optional_missing: int = 0
    optional_missing_packages: list[str] = Field(default_factory=list)

    # Full tree for detailed reports
    tree: Any  # Rich Tree object - not JSON serializable

    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    max_depth: int = 50
    version: Optional[str] = None

    # Display options
    missing_only: bool = False

    @cached_property
    def required_missing_packages(self) -> set[str]:
        """Get the set of required (non-optional) missing packages."""
        return set(self.missing_packages) - set(self.optional_missing_packages)

    @cached_property
    def optional_missing_set(self) -> set[str]:
        """Get the set of optional missing packages."""
        return set(self.optional_missing_packages)

    @cached_property
    def unique_packaged_packages(self) -> set[str]:
        """Get the unique set of packaged packages."""
        return set(self.packaged_packages)


class Reporter(ABC):
    """
    Abstract base class for report generators.

    Each report format (stdout, markdown, json, etc.) must implement this interface.

    Attributes:
        name: Short identifier for the format (e.g., "json", "markdown")
        description: Human-readable description
        file_extension: File extension for output files (None for stdout)
        writes_to_file: Whether this reporter writes to a file
    """

    # Class attributes that must be defined by subclasses
    name: str
    description: str
    file_extension: Optional[str] = None
    writes_to_file: bool = False

    @abstractmethod
    def generate(self, data: ReportData) -> str:
        """
        Generate the report content.

        Args:
            data: Report data containing all information.

        Returns:
            Report content as a string.
        """
        pass

    def get_output_filename(self, data: ReportData) -> str:
        """
        Get the output filename for file-based reporters.

        Args:
            data: Report data.

        Returns:
            Filename string.
        """
        timestamp = data.timestamp.strftime("%Y%m%d_%H%M%S")
        return f"woolly_{data.root_package}_{timestamp}.{self.file_extension}"

    def write_report(
        self, data: ReportData, output_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Write the report to a file.

        Args:
            data: Report data.
            output_dir: Directory to write to. Defaults to current directory.

        Returns:
            Path to the written file, or None for stdout reporters.
        """
        if not self.writes_to_file:
            return None

        content = self.generate(data)
        output_dir = output_dir or Path.cwd()
        output_path = output_dir / self.get_output_filename(data)
        output_path.write_text(content)
        return output_path

    # ----------------------------------------------------------------
    # Shared tree traversal utilities for subclasses
    # ----------------------------------------------------------------

    def _get_label(self, node) -> str:
        """
        Extract the label text from a tree node, handling nested Trees.

        Args:
            node: A Rich Tree node or string.

        Returns:
            The label text as a string.
        """
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
        """
        Get all children from a tree node, flattening nested Trees.

        Args:
            node: A Rich Tree node.

        Returns:
            List of child nodes.
        """
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

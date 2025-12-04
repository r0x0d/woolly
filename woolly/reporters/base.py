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

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class PackageStatus(BaseModel):
    """Status of a single package in the dependency tree."""

    name: str
    version: Optional[str] = None
    is_packaged: bool
    fedora_versions: list[str] = Field(default_factory=list)
    fedora_packages: list[str] = Field(default_factory=list)
    is_visited: bool = False
    not_found: bool = False


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
    packages: list[PackageStatus] = Field(default_factory=list)

    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    max_depth: int = 50
    version: Optional[str] = None


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

"""
Template-based report generator using Jinja2.

Allows users to provide a custom markdown template file for report generation.
Only a limited set of variables are exposed for security and simplicity.
"""

from pathlib import Path
from typing import Optional

from woolly.reporters.base import ReportData, Reporter, strip_markup


class TemplateReporter(Reporter):
    """Reporter that generates reports from user-provided Jinja2 templates.

    This reporter allows users to customize the output format by providing
    a markdown template file. Only a limited, safe set of variables are
    exposed to the template.

    Available template variables:
        Metadata:
            - root_package: Name of the analyzed package
            - language: Language/ecosystem name (e.g., "Rust", "Python")
            - registry: Registry name (e.g., "crates.io", "PyPI")
            - version: Package version (if specified)
            - timestamp: Formatted timestamp string (YYYY-MM-DD HH:MM:SS)
            - max_depth: Maximum recursion depth used

        Statistics:
            - total_dependencies: Total number of dependencies analyzed
            - packaged_count: Number of packages available in Fedora
            - missing_count: Number of packages missing from Fedora

        Optional dependency statistics:
            - include_optional: Whether optional deps were included
            - optional_total: Total optional dependencies
            - optional_packaged: Optional deps available in Fedora
            - optional_missing: Optional deps missing from Fedora

        Package lists (sorted):
            - missing_packages: List of missing required package names
            - packaged_packages: List of packaged package names
            - optional_missing_packages: List of missing optional package names

        Flags:
            - missing_only: Whether missing-only mode was enabled

    Example template:
        # Report for {{ root_package }}

        Generated: {{ timestamp }}
        Language: {{ language }}

        ## Summary
        - Total: {{ total_dependencies }}
        - Packaged: {{ packaged_count }}
        - Missing: {{ missing_count }}

        {% if missing_packages %}
        ## Missing Packages
        {% for pkg in missing_packages %}
        - {{ pkg }}
        {% endfor %}
        {% endif %}
    """

    name = "template"
    description = "Custom template-based report (requires --template)"
    file_extension = "md"
    writes_to_file = True

    def __init__(self, template_path: Optional[Path] = None):
        """Initialize the template reporter.

        Args:
            template_path: Path to the Jinja2 template file.
        """
        self._template_path = template_path
        self._jinja2_available: Optional[bool] = None

    @property
    def template_path(self) -> Optional[Path]:
        """Get the template path."""
        return self._template_path

    @template_path.setter
    def template_path(self, value: Optional[Path]) -> None:
        """Set the template path."""
        self._template_path = value

    def _check_jinja2(self) -> bool:
        """Check if Jinja2 is available.

        Returns:
            True if Jinja2 is available, False otherwise.
        """
        if self._jinja2_available is None:
            try:
                import jinja2  # type: ignore[import-not-found]  # noqa: F401

                self._jinja2_available = True
            except ImportError:
                self._jinja2_available = False
        return self._jinja2_available

    def _get_template_context(self, data: ReportData) -> dict:
        """Build the template context with allowed variables only.

        This method creates a safe, limited context for template rendering.
        Only specific variables from ReportData are exposed.

        Args:
            data: Report data containing all information.

        Returns:
            Dictionary of template variables.
        """
        return {
            # Metadata
            "root_package": data.root_package,
            "language": data.language,
            "registry": data.registry,
            "version": data.version,
            "timestamp": data.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "max_depth": data.max_depth,
            # Statistics
            "total_dependencies": data.total_dependencies,
            "packaged_count": data.packaged_count,
            "missing_count": data.missing_count,
            # Optional dependency statistics
            "include_optional": data.include_optional,
            "optional_total": data.optional_total,
            "optional_packaged": data.optional_packaged,
            "optional_missing": data.optional_missing,
            # Package lists (sorted for consistent output)
            "missing_packages": sorted(data.required_missing_packages),
            "packaged_packages": sorted(data.unique_packaged_packages),
            "optional_missing_packages": sorted(data.optional_missing_set),
            # Flags
            "missing_only": data.missing_only,
        }

    def generate(self, data: ReportData) -> str:
        """Generate report content from the template.

        Args:
            data: Report data containing all information.

        Returns:
            Rendered template content as a string.

        Raises:
            RuntimeError: If Jinja2 is not installed or template is not set.
            FileNotFoundError: If the template file doesn't exist.
            jinja2.TemplateError: If there's a template syntax error.
        """
        if not self._check_jinja2():
            raise RuntimeError(
                "Jinja2 is required for template reports. "
                "Install it with: pip install jinja2"
            )

        if self._template_path is None:
            raise RuntimeError(
                "No template path specified. Use --template to provide a template file."
            )

        if not self._template_path.exists():
            raise FileNotFoundError(f"Template file not found: {self._template_path}")

        # Import Jinja2 here (we've already checked it's available)
        from jinja2 import (  # type: ignore[import-not-found]
            Environment,
            FileSystemLoader,
            StrictUndefined,
            select_autoescape,
        )

        # Create Jinja2 environment with security settings
        env = Environment(
            loader=FileSystemLoader(self._template_path.parent),
            autoescape=select_autoescape(default=False),
            undefined=StrictUndefined,  # Raise error on undefined variables
            # Disable dangerous features
            extensions=[],
        )

        # Add custom filter to strip Rich markup
        env.filters["strip_markup"] = strip_markup

        # Load and render template
        template = env.get_template(self._template_path.name)
        context = self._get_template_context(data)

        return template.render(**context)

    def get_output_filename(self, data: ReportData) -> str:
        """Get the output filename for the template report.

        Uses the template filename as a base if available, otherwise
        falls back to the default naming convention.

        Args:
            data: Report data.

        Returns:
            Filename string.
        """
        timestamp = data.timestamp.strftime("%Y%m%d_%H%M%S")
        if self._template_path:
            # Use template name as base (without extension)
            base_name = self._template_path.stem
            return f"woolly_{data.root_package}_{base_name}_{timestamp}.md"
        return f"woolly_{data.root_package}_template_{timestamp}.md"

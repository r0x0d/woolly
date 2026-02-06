"""
JSON report generator.

Generates a JSON file with structured data for machine consumption.
"""

import re
from typing import Optional

from pydantic import BaseModel, Field

from woolly.reporters.base import ReportData, Reporter, strip_markup


class TreeNodeData(BaseModel):
    """Structured data for a single node in the dependency tree."""

    raw: str
    name: Optional[str] = None
    version: Optional[str] = None
    license: Optional[str] = None
    optional: bool = False
    status: Optional[str] = None
    is_packaged: Optional[bool] = None
    fedora_versions: list[str] = Field(default_factory=list)
    fedora_packages: list[str] = Field(default_factory=list)
    dependencies: list["TreeNodeData"] = Field(default_factory=list)


class ReportMetadata(BaseModel):
    """Metadata for the JSON report."""

    generated_at: str
    tool: str = "woolly"
    root_package: str
    language: str
    registry: str
    license: Optional[str] = None
    version: Optional[str] = None
    max_depth: int
    include_optional: bool
    missing_only: bool = False


class DevBuildDepData(BaseModel):
    """Structured data for a dev or build dependency."""

    name: str
    version_requirement: str
    is_packaged: bool
    fedora_versions: list[str] = Field(default_factory=list)
    fedora_packages: list[str] = Field(default_factory=list)


class FeatureData(BaseModel):
    """Structured data for a feature flag or extra."""

    name: str
    dependencies: list[str] = Field(default_factory=list)


class ReportSummary(BaseModel):
    """Summary statistics for the JSON report."""

    total_dependencies: int
    packaged_count: int
    missing_count: int
    optional: "OptionalSummary"
    dev: "DevBuildSummary"
    build: "DevBuildSummary"


class OptionalSummary(BaseModel):
    """Optional dependency statistics."""

    total: int
    packaged: int
    missing: int


class DevBuildSummary(BaseModel):
    """Dev or build dependency statistics."""

    total: int
    packaged: int
    missing: int


class JsonReport(BaseModel):
    """Complete JSON report structure."""

    metadata: ReportMetadata
    summary: ReportSummary
    missing_packages: list[str]
    missing_optional_packages: list[str]
    packaged_packages: list[str]
    features: list[FeatureData] = Field(default_factory=list)
    dev_dependencies: list[DevBuildDepData] = Field(default_factory=list)
    build_dependencies: list[DevBuildDepData] = Field(default_factory=list)
    dependency_tree: TreeNodeData


class JsonReporter(Reporter):
    """Reporter that generates a JSON file."""

    name = "json"
    description = "JSON report file (machine-readable)"
    file_extension = "json"
    writes_to_file = True

    def generate(self, data: ReportData) -> str:
        """Generate JSON report content."""
        # Convert features to FeatureData
        features_data = []
        for f in data.features:
            if hasattr(f, "name"):
                features_data.append(
                    FeatureData(name=f.name, dependencies=f.dependencies)
                )
            else:
                features_data.append(
                    FeatureData(
                        name=f.get("name", ""), dependencies=f.get("dependencies", [])
                    )
                )

        # Convert dev/build deps to DevBuildDepData
        dev_deps_data = [
            DevBuildDepData(
                name=d["name"],
                version_requirement=d["version_requirement"],
                is_packaged=d["is_packaged"],
                fedora_versions=d.get("fedora_versions", []),
                fedora_packages=d.get("fedora_packages", []),
            )
            for d in data.dev_dependencies
        ]
        build_deps_data = [
            DevBuildDepData(
                name=d["name"],
                version_requirement=d["version_requirement"],
                is_packaged=d["is_packaged"],
                fedora_versions=d.get("fedora_versions", []),
                fedora_packages=d.get("fedora_packages", []),
            )
            for d in data.build_dependencies
        ]

        report = JsonReport(
            metadata=ReportMetadata(
                generated_at=data.timestamp.isoformat(),
                root_package=data.root_package,
                language=data.language,
                registry=data.registry,
                license=data.root_license,
                version=data.version,
                max_depth=data.max_depth,
                include_optional=data.include_optional,
                missing_only=data.missing_only,
            ),
            summary=ReportSummary(
                total_dependencies=data.total_dependencies,
                packaged_count=data.packaged_count,
                missing_count=data.missing_count,
                optional=OptionalSummary(
                    total=data.optional_total,
                    packaged=data.optional_packaged,
                    missing=data.optional_missing,
                ),
                dev=DevBuildSummary(
                    total=data.dev_total,
                    packaged=data.dev_packaged,
                    missing=data.dev_missing,
                ),
                build=DevBuildSummary(
                    total=data.build_total,
                    packaged=data.build_packaged,
                    missing=data.build_missing,
                ),
            ),
            missing_packages=sorted(data.required_missing_packages),
            missing_optional_packages=sorted(data.optional_missing_set),
            # Skip packaged packages list when missing_only mode is enabled
            packaged_packages=[]
            if data.missing_only
            else sorted(data.unique_packaged_packages),
            features=features_data,
            dev_dependencies=dev_deps_data,
            build_dependencies=build_deps_data,
            dependency_tree=self._tree_to_model(data.tree),
        )

        return report.model_dump_json(indent=2)

    def _tree_to_model(self, tree) -> TreeNodeData:
        """Convert Rich Tree to TreeNodeData model."""
        label = self._get_label(tree)
        node_data = self._parse_label(label)

        # Get children using inherited method
        children = self._get_children(tree)

        if children:
            node_data.dependencies = [self._tree_to_model(child) for child in children]

        return node_data

    def _parse_label(self, label: str) -> TreeNodeData:
        """Parse a tree label into structured TreeNodeData."""
        # Strip Rich markup using shared utility
        clean_label = strip_markup(label)

        node = TreeNodeData(raw=clean_label.strip())

        # Check if this is an optional dependency
        node.optional = "(optional)" in clean_label

        # Try to extract license from the label (format: "(LICENSE)" before optional/status)
        license_match = re.search(
            r"v[\d.]+\s*\(([^)]+)\)\s*(?:\(optional\))?\s*•", clean_label
        )
        if license_match:
            potential_license = license_match.group(1)
            # Make sure it's not a version number or "optional"
            if potential_license != "optional" and not re.match(
                r"^[\d., ]+$", potential_license
            ):
                node.license = potential_license

        # Try to extract package name and version
        # Pattern: "package_name vX.Y.Z (LICENSE) (optional) • status" or "package_name vX.Y.Z • status"
        match = re.match(
            r"^(\S+)\s*(?:v([\d.]+))?\s*(?:\([^)]*\))?\s*(?:\(optional\))?\s*•\s*(.+)$",
            clean_label.strip(),
        )
        if match:
            node.name = match.group(1)
            if match.group(2):
                node.version = match.group(2)

            status_text = match.group(3).strip()
            if (
                "packaged" in status_text.lower()
                and "not packaged" not in status_text.lower()
            ):
                node.status = "packaged"
                # Try to extract Fedora versions
                ver_match = re.search(r"\(([\d., ]+)\)", status_text)
                if ver_match:
                    node.fedora_versions = [
                        v.strip() for v in ver_match.group(1).split(",")
                    ]
                # Try to extract package names
                pkg_match = re.search(r"\[([^\]]+)\]", status_text)
                if pkg_match:
                    node.fedora_packages = [
                        p.strip() for p in pkg_match.group(1).split(",")
                    ]
            elif "not packaged" in status_text.lower():
                node.status = "not_packaged"
            elif "not found" in status_text.lower():
                node.status = "not_found"
            elif "already visited" in status_text.lower():
                node.status = "visited"
                node.is_packaged = "✓" in status_text
        else:
            # Simpler patterns
            if "already visited" in clean_label:
                node.status = "visited"
                node.is_packaged = "✓" in clean_label
            elif "max depth" in clean_label:
                node.status = "max_depth_reached"

        return node

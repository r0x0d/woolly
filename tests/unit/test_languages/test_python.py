"""
Unit tests for woolly.languages.python module.

Tests cover:
- Good path: fetching package info and dependencies
- Critical path: requirement parsing, name normalization
- Bad path: 404 responses, API errors, malformed requirements
"""

import pytest

from woolly.languages.base import Dependency, FeatureInfo, PackageInfo
from woolly.languages.python import PythonProvider


class TestPythonProviderAttributes:
    """Tests for PythonProvider class attributes."""

    @pytest.mark.unit
    def test_provider_attributes(self):
        """Good path: provider has correct attributes."""
        provider = PythonProvider()
        assert provider.name == "python"
        assert provider.display_name == "Python"
        assert provider.registry_name == "PyPI"
        assert provider.fedora_provides_prefix == "python3dist"
        assert provider.cache_namespace == "pypi"


class TestPythonProviderFetchPackageInfo:
    """Tests for PythonProvider.fetch_package_info method."""

    @pytest.mark.unit
    def test_returns_package_info(
        self, temp_cache_dir, mocker, make_httpx_response, mock_pypi_response
    ):
        """Good path: returns PackageInfo for existing package."""
        provider = PythonProvider()

        response = make_httpx_response(200, mock_pypi_response)
        mocker.patch("woolly.http.get", return_value=response)

        info = provider.fetch_package_info("requests")

        assert isinstance(info, PackageInfo)
        assert info.name == "requests"
        assert info.latest_version == "2.31.0"
        assert info.description is not None and "HTTP" in info.description
        assert info.license == "Apache-2.0"

    @pytest.mark.unit
    def test_returns_none_for_404(self, temp_cache_dir, mocker, make_httpx_response):
        """Bad path: returns None for non-existent package."""
        provider = PythonProvider()

        response = make_httpx_response(404)
        mocker.patch("woolly.http.get", return_value=response)

        info = provider.fetch_package_info("nonexistent-package-12345")

        assert info is None

    @pytest.mark.unit
    def test_raises_on_server_error(self, temp_cache_dir, mocker, make_httpx_response):
        """Bad path: raises RuntimeError on server error."""
        provider = PythonProvider()

        response = make_httpx_response(500)
        mocker.patch("woolly.http.get", return_value=response)

        with pytest.raises(RuntimeError) as exc_info:
            provider.fetch_package_info("some-package")

        assert "500" in str(exc_info.value)

    @pytest.mark.unit
    def test_uses_cache(
        self, temp_cache_dir, mocker, make_httpx_response, mock_pypi_response
    ):
        """Critical path: uses cached data on subsequent calls."""
        provider = PythonProvider()

        response = make_httpx_response(200, mock_pypi_response)
        mock_get = mocker.patch("woolly.http.get", return_value=response)

        provider.fetch_package_info("requests")
        provider.fetch_package_info("requests")

        assert mock_get.call_count == 1


class TestPythonProviderFetchDependencies:
    """Tests for PythonProvider.fetch_dependencies method."""

    @pytest.mark.unit
    def test_returns_dependencies(
        self, temp_cache_dir, mocker, make_httpx_response, mock_pypi_response
    ):
        """Good path: returns list of dependencies."""
        provider = PythonProvider()

        response = make_httpx_response(200, mock_pypi_response)
        mocker.patch("woolly.http.get", return_value=response)

        deps = provider.fetch_dependencies("requests", "2.31.0")

        assert len(deps) >= 4  # charset-normalizer, idna, urllib3, certifi
        assert all(isinstance(d, Dependency) for d in deps)

        # Check a specific dependency
        dep_names = [d.name for d in deps]
        assert "idna" in dep_names

    @pytest.mark.unit
    def test_marks_extras_as_optional(
        self, temp_cache_dir, mocker, make_httpx_response, mock_pypi_response
    ):
        """Critical path: dependencies with extras are marked optional."""
        provider = PythonProvider()

        response = make_httpx_response(200, mock_pypi_response)
        mocker.patch("woolly.http.get", return_value=response)

        deps = provider.fetch_dependencies("requests", "2.31.0")

        # PySocks is an extra dependency
        socks_deps = [d for d in deps if "pysocks" in d.name.lower()]
        if socks_deps:
            assert socks_deps[0].optional is True

    @pytest.mark.unit
    def test_returns_empty_on_error(self, temp_cache_dir, mocker, make_httpx_response):
        """Bad path: returns empty list on API error."""
        provider = PythonProvider()

        response = make_httpx_response(404)
        mocker.patch("woolly.http.get", return_value=response)

        deps = provider.fetch_dependencies("nonexistent", "1.0.0")

        assert deps == []

    @pytest.mark.unit
    def test_handles_no_requires_dist(
        self, temp_cache_dir, mocker, make_httpx_response
    ):
        """Good path: handles packages with no dependencies."""
        provider = PythonProvider()

        response_data = {
            "info": {
                "name": "simple-pkg",
                "version": "1.0.0",
                "summary": "Simple package",
                "requires_dist": None,
            }
        }
        response = make_httpx_response(200, response_data)
        mocker.patch("woolly.http.get", return_value=response)

        deps = provider.fetch_dependencies("simple-pkg", "1.0.0")

        assert deps == []


class TestPythonProviderParseRequirement:
    """Tests for PythonProvider._parse_requirement method."""

    @pytest.fixture
    def provider(self):
        return PythonProvider()

    @pytest.mark.unit
    def test_simple_requirement(self, provider):
        """Good path: parses simple requirement."""
        dep = provider._parse_requirement("requests")

        assert dep.name == "requests"
        assert dep.version_requirement == "*"
        assert dep.optional is False

    @pytest.mark.unit
    def test_requirement_with_version(self, provider):
        """Good path: parses requirement with version."""
        dep = provider._parse_requirement("requests>=2.20.0")

        assert dep.name == "requests"
        assert dep.version_requirement == ">=2.20.0"

    @pytest.mark.unit
    def test_requirement_with_complex_version(self, provider):
        """Good path: parses complex version specifier."""
        dep = provider._parse_requirement("urllib3<3,>=1.21.1")

        assert dep.name == "urllib3"
        assert "<3,>=1.21.1" in dep.version_requirement

    @pytest.mark.unit
    def test_requirement_with_extras(self, provider):
        """Good path: parses requirement with extras marker."""
        dep = provider._parse_requirement("PySocks>=1.5.6; extra == 'socks'")

        assert dep.name == "pysocks"  # Normalized
        assert dep.optional is True
        assert (
            dep.kind == "normal"
        )  # Keep as normal so --optional flag can include them
        assert dep.group == "socks"

    @pytest.mark.unit
    def test_requirement_with_python_version_marker(self, provider):
        """Good path: parses requirement with environment marker."""
        dep = provider._parse_requirement("typing-extensions; python_version < '3.8'")

        assert dep.name == "typing-extensions"
        assert dep.optional is False  # Not an extra

    @pytest.mark.unit
    def test_requirement_with_package_extras(self, provider):
        """Good path: strips extras from package name."""
        dep = provider._parse_requirement("package[extra1,extra2]>=1.0")

        assert dep.name == "package"
        assert "[" not in dep.name

    @pytest.mark.unit
    def test_invalid_requirement(self, provider):
        """Bad path: returns None for invalid requirement."""
        dep = provider._parse_requirement("!!!invalid!!!")

        assert dep is None


class TestPythonProviderNormalizePackageName:
    """Tests for PythonProvider.normalize_package_name method."""

    @pytest.fixture
    def provider(self):
        return PythonProvider()

    @pytest.mark.unit
    def test_lowercase(self, provider):
        """Good path: converts to lowercase."""
        assert provider.normalize_package_name("MyPackage") == "mypackage"

    @pytest.mark.unit
    def test_underscore_to_hyphen(self, provider):
        """Critical path: converts underscores to hyphens."""
        assert provider.normalize_package_name("my_package") == "my-package"

    @pytest.mark.unit
    def test_dot_to_hyphen(self, provider):
        """Critical path: converts dots to hyphens."""
        assert provider.normalize_package_name("my.package") == "my-package"

    @pytest.mark.unit
    def test_multiple_separators(self, provider):
        """Critical path: normalizes multiple consecutive separators."""
        assert provider.normalize_package_name("my__package") == "my-package"
        assert provider.normalize_package_name("my--package") == "my-package"
        assert provider.normalize_package_name("my_.package") == "my-package"

    @pytest.mark.unit
    def test_mixed_case_and_separators(self, provider):
        """Good path: handles mixed case and separators."""
        result = provider.normalize_package_name("My_Package.Name")
        assert result == "my-package-name"


class TestPythonProviderAlternativeNames:
    """Tests for PythonProvider.get_alternative_names method."""

    @pytest.fixture
    def provider(self):
        return PythonProvider()

    @pytest.mark.unit
    def test_hyphen_to_underscore(self, provider):
        """Critical path: suggests underscore variant."""
        alternatives = provider.get_alternative_names("my-package")

        assert "my_package" in alternatives

    @pytest.mark.unit
    def test_hyphen_to_dot(self, provider):
        """Critical path: suggests dot variant."""
        alternatives = provider.get_alternative_names("my-package")

        assert "my.package" in alternatives

    @pytest.mark.unit
    def test_no_alternatives_for_simple(self, provider):
        """Good path: no alternatives for simple names."""
        alternatives = provider.get_alternative_names("requests")

        assert alternatives == []


class TestPythonProviderFetchFeatures:
    """Tests for PythonProvider.fetch_features method."""

    @pytest.mark.unit
    def test_returns_features(
        self, temp_cache_dir, mocker, make_httpx_response, mock_pypi_version_response
    ):
        """Good path: returns list of FeatureInfo (extras)."""
        provider = PythonProvider()

        response = make_httpx_response(200, mock_pypi_version_response)
        mocker.patch("woolly.http.get", return_value=response)

        features = provider.fetch_features("requests", "2.31.0")

        assert len(features) == 2
        assert all(isinstance(f, FeatureInfo) for f in features)

        feature_names = [f.name for f in features]
        assert "socks" in feature_names
        assert "security" in feature_names

        # Check socks extra has PySocks
        socks = next(f for f in features if f.name == "socks")
        assert "pysocks" in socks.dependencies

        # Check security extra has its deps
        security = next(f for f in features if f.name == "security")
        assert "pyopenssl" in security.dependencies
        assert "cryptography" in security.dependencies

    @pytest.mark.unit
    def test_returns_empty_on_error(self, temp_cache_dir, mocker, make_httpx_response):
        """Bad path: returns empty list on API error."""
        provider = PythonProvider()

        response = make_httpx_response(404)
        mocker.patch("woolly.http.get", return_value=response)

        features = provider.fetch_features("nonexistent", "1.0.0")

        assert features == []

    @pytest.mark.unit
    def test_uses_cache(
        self, temp_cache_dir, mocker, make_httpx_response, mock_pypi_version_response
    ):
        """Critical path: uses cached features."""
        provider = PythonProvider()

        response = make_httpx_response(200, mock_pypi_version_response)
        mock_get = mocker.patch("woolly.http.get", return_value=response)

        provider.fetch_features("requests", "2.31.0")
        provider.fetch_features("requests", "2.31.0")

        assert mock_get.call_count == 1


class TestPythonProviderLicense:
    """Tests for license extraction in PythonProvider."""

    @pytest.mark.unit
    def test_license_from_license_field(
        self, temp_cache_dir, mocker, make_httpx_response, mock_pypi_response
    ):
        """Good path: license is extracted from license field."""
        provider = PythonProvider()

        response = make_httpx_response(200, mock_pypi_response)
        mocker.patch("woolly.http.get", return_value=response)

        info = provider.fetch_package_info("requests")

        assert info.license == "Apache-2.0"

    @pytest.mark.unit
    def test_license_prefers_license_expression(
        self, temp_cache_dir, mocker, make_httpx_response
    ):
        """Good path: license_expression takes precedence over license."""
        provider = PythonProvider()

        response_data = {
            "info": {
                "name": "modern-pkg",
                "version": "1.0.0",
                "summary": "Modern package",
                "license": "MIT License",
                "license_expression": "MIT",
            }
        }
        response = make_httpx_response(200, response_data)
        mocker.patch("woolly.http.get", return_value=response)

        info = provider.fetch_package_info("modern-pkg")

        assert info.license == "MIT"

    @pytest.mark.unit
    def test_license_none_when_missing(
        self, temp_cache_dir, mocker, make_httpx_response
    ):
        """Good path: license is None when not in response."""
        provider = PythonProvider()

        response_data = {
            "info": {
                "name": "no-license",
                "version": "1.0.0",
                "summary": "No license",
            }
        }
        response = make_httpx_response(200, response_data)
        mocker.patch("woolly.http.get", return_value=response)

        info = provider.fetch_package_info("no-license")

        assert info.license is None

    @pytest.mark.unit
    def test_license_full_text_falls_back_to_classifiers(
        self, temp_cache_dir, mocker, make_httpx_response
    ):
        """Good path: full license text in 'license' field is ignored; classifiers are used."""
        provider = PythonProvider()

        full_text = (
            "MIT License\n\n"
            "Copyright (c) 2023 Example\n\n"
            "Permission is hereby granted, free of charge, to any person obtaining a copy "
            "of this software..."
        )
        response_data = {
            "info": {
                "name": "old-pkg",
                "version": "1.0.0",
                "summary": "Old package with full license text",
                "license": full_text,
                "classifiers": [
                    "Programming Language :: Python :: 3",
                    "License :: OSI Approved :: MIT License",
                ],
            }
        }
        response = make_httpx_response(200, response_data)
        mocker.patch("woolly.http.get", return_value=response)

        info = provider.fetch_package_info("old-pkg")

        assert info.license == "MIT"

    @pytest.mark.unit
    def test_license_full_text_no_classifiers_returns_none(
        self, temp_cache_dir, mocker, make_httpx_response
    ):
        """Edge case: full license text with no classifiers returns None."""
        provider = PythonProvider()

        full_text = (
            "BSD 3-Clause License\n\n"
            "Redistribution and use in source and binary forms..."
        )
        response_data = {
            "info": {
                "name": "old-pkg2",
                "version": "1.0.0",
                "summary": "Old package with full text and no classifiers",
                "license": full_text,
            }
        }
        response = make_httpx_response(200, response_data)
        mocker.patch("woolly.http.get", return_value=response)

        info = provider.fetch_package_info("old-pkg2")

        assert info.license is None

    @pytest.mark.unit
    def test_license_short_name_accepted(
        self, temp_cache_dir, mocker, make_httpx_response
    ):
        """Good path: short license name in 'license' field is kept as-is."""
        provider = PythonProvider()

        response_data = {
            "info": {
                "name": "some-pkg",
                "version": "1.0.0",
                "summary": "Package with short license",
                "license": "BSD-3-Clause",
            }
        }
        response = make_httpx_response(200, response_data)
        mocker.patch("woolly.http.get", return_value=response)

        info = provider.fetch_package_info("some-pkg")

        assert info.license == "BSD-3-Clause"

    @pytest.mark.unit
    def test_license_from_classifiers_when_license_field_empty(
        self, temp_cache_dir, mocker, make_httpx_response
    ):
        """Good path: classifiers used when license field is empty string."""
        provider = PythonProvider()

        response_data = {
            "info": {
                "name": "classified-pkg",
                "version": "1.0.0",
                "summary": "Package with empty license field",
                "license": "",
                "classifiers": [
                    "License :: OSI Approved :: Apache Software License",
                ],
            }
        }
        response = make_httpx_response(200, response_data)
        mocker.patch("woolly.http.get", return_value=response)

        info = provider.fetch_package_info("classified-pkg")

        assert info.license == "Apache-2.0"


class TestPythonProviderExtraGroupParsing:
    """Tests for extra group association in dependency parsing."""

    @pytest.fixture
    def provider(self):
        return PythonProvider()

    @pytest.mark.unit
    def test_group_set_for_extra_dependency(self, provider):
        """Good path: group is set for extra-gated dependency."""
        dep = provider._parse_requirement("PySocks>=1.5.6; extra == 'socks'")

        assert dep.group == "socks"

    @pytest.mark.unit
    def test_group_none_for_normal_dependency(self, provider):
        """Good path: group is None for normal dependency."""
        dep = provider._parse_requirement("requests>=2.20.0")

        assert dep.group is None

    @pytest.mark.unit
    def test_group_none_for_env_marker_only(self, provider):
        """Good path: group is None for environment marker (not extra)."""
        dep = provider._parse_requirement("typing-extensions; python_version < '3.8'")

        assert dep.group is None

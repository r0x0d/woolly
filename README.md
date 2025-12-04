# 🐑 Woolly

**Check if package dependencies are available in Fedora.**

Woolly analyzes package dependencies from various language ecosystems and checks their availability in Fedora repositories, helping packagers estimate the effort needed to bring a package to Fedora.

> ⚠️ **Experimental Software**
>
> This project is still experimental and may not get things right all the time.
> Results should be verified manually, especially for complex dependency trees.
> Platform-specific dependencies (like `windows-*` crates) may be flagged as missing
> even though they're not needed on Linux.

## What does "woolly" mean?

Nothing. I just liked the name. 🐑

## Features

- **Multi-language support** — Analyze dependencies from Rust (crates.io) and Python (PyPI)
- **Multiple output formats** — Console output, JSON, and Markdown reports
- **Optional dependency tracking** — Optionally include and separately track optional dependencies
- **Smart caching** — Caches API responses and dnf queries to speed up repeated analyses
- **Progress tracking** — Real-time progress bar showing analysis status
- **Debug logging** — Verbose logging mode for troubleshooting
- **Extensible architecture** — Easy to add new languages and report formats

## Supported Languages

| Language | Registry  | CLI Flag              | Aliases                 |
|----------|-----------|-----------------------|-------------------------|
| Rust     | crates.io | `--lang rust`         | `-l rs`, `-l crate`     |
| Python   | PyPI      | `--lang python`       | `-l py`, `-l pypi`      |

## Output Formats

| Format   | Description                      | CLI Flag             | Aliases              |
|----------|----------------------------------|----------------------|----------------------|
| stdout   | Rich console output (default)    | `--report stdout`    | `-r console`         |
| json     | JSON file for programmatic use   | `--report json`      |                      |
| markdown | Markdown file for documentation  | `--report markdown`  | `-r md`              |

## Installation

```bash
# Using uv (recommended)
uv pip install .

# Or run directly without installing
uv run woolly --help

# Using pip
pip install .
```

### Requirements

- Python 3.10+
- `dnf` available on the system (for Fedora package queries)

## Usage

### Basic Usage

```bash
# Check a Rust crate (default language)
woolly check ripgrep

# Check a Python package
woolly check --lang python requests

# Use language aliases
woolly check -l py flask
woolly check -l rs tokio
```

### Options

```bash
# Check a specific version
woolly check serde --version 1.0.200

# Include optional dependencies in the analysis
woolly check --optional requests -l python

# Limit recursion depth
woolly check --max-depth 10 tokio

# Disable progress bar
woolly check --no-progress serde

# Enable debug logging
woolly check --debug flask -l py

# Output as JSON
woolly check --report json serde

# Output as Markdown
woolly check -r md requests -l py
```

### Other Commands

```bash
# List available languages
woolly list-languages

# List available output formats
woolly list-formats

# Clear the cache
woolly clear-cache
```

## Example Output

### Rust

```bash
$ woolly check cliclack

Analyzing Rust package: cliclack
Registry: crates.io
Cache directory: /home/user/.cache/woolly

  Analyzing Rust dependencies ━━━━━━━━━━━━━━━━━ 100% • 0:00:15 complete!

  Dependency Summary for 'cliclack' (Rust)
╭────────────────────────────┬───────╮
│ Metric                     │ Value │
├────────────────────────────┼───────┤
│ Total dependencies checked │     7 │
│ Packaged in Fedora         │     0 │
│ Missing from Fedora        │     1 │
╰────────────────────────────┴───────╯

Missing packages that need packaging:
  • cliclack

Dependency Tree:
cliclack v0.3.6 • ✗ not packaged
├── console v0.16.1 • ✓ packaged (0.16.1)
│   ├── encode_unicode v1.0.0 • ✓ packaged (1.0.0)
│   └── windows-sys v0.61.2 • ✗ not packaged
...
```

### Python

```bash
$ woolly check --lang python requests

Analyzing Python package: requests
Registry: PyPI
Cache directory: /home/user/.cache/woolly

  Analyzing Python dependencies ━━━━━━━━━━━━━━ 100% • 0:00:05 complete!

  Dependency Summary for 'requests' (Python)
╭────────────────────────────┬───────╮
│ Metric                     │ Value │
├────────────────────────────┼───────┤
│ Total dependencies checked │     5 │
│ Packaged in Fedora         │     5 │
│ Missing from Fedora        │     0 │
╰────────────────────────────┴───────╯

Dependency Tree:
requests v2.32.3 • ✓ packaged (2.32.3) [python3-requests]
├── charset-normalizer v3.4.0 • ✓ packaged (3.4.0) [python3-charset-normalizer]
├── idna v3.10 • ✓ packaged (3.10) [python3-idna]
├── urllib3 v2.2.3 • ✓ packaged (2.2.3) [python3-urllib3]
└── certifi v2024.8.30 • ✓ packaged (2024.8.30) [python3-certifi]
```

### With Optional Dependencies

```bash
$ woolly check --lang python --optional flask

  Dependency Summary for 'flask' (Python)
╭────────────────────────────┬───────╮
│ Metric                     │ Value │
├────────────────────────────┼───────┤
│ Total dependencies checked │    15 │
│ Packaged in Fedora         │    12 │
│ Missing from Fedora        │     3 │
│                            │       │
│ Optional dependencies      │     4 │
│   ├─ Packaged              │     2 │
│   └─ Missing               │     2 │
╰────────────────────────────┴───────╯
```

## Adding a New Language

To add support for a new language, create a new provider in `woolly/languages/`:

```python
# woolly/languages/go.py
from typing import Optional

from woolly.languages.base import Dependency, LanguageProvider, PackageInfo


class GoProvider(LanguageProvider):
    """Provider for Go modules."""

    # Required class attributes
    name = "go"
    display_name = "Go"
    registry_name = "Go Modules"
    fedora_provides_prefix = "golang"
    cache_namespace = "go"

    # Required methods to implement:

    def fetch_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """Fetch package info from proxy.golang.org."""
        ...

    def fetch_dependencies(self, package_name: str, version: str) -> list[Dependency]:
        """Fetch dependencies from go.mod."""
        ...

    # Optional: Override these if your language has special naming conventions

    def normalize_package_name(self, package_name: str) -> str:
        """Normalize package name for Fedora lookup."""
        return package_name

    def get_alternative_names(self, package_name: str) -> list[str]:
        """Alternative names to try if package not found."""
        return []
```

Then register it in `woolly/languages/__init__.py`:

```python
from woolly.languages.go import GoProvider

PROVIDERS: dict[str, type[LanguageProvider]] = {
    "rust": RustProvider,
    "python": PythonProvider,
    "go": GoProvider,  # Add new provider
}

ALIASES: dict[str, str] = {
    # ... existing aliases
    "golang": "go",
}
```

## Adding a New Output Format

To add a new output format, create a reporter in `woolly/reporters/`:

```python
# woolly/reporters/html.py
from woolly.reporters.base import Reporter, ReportData


class HtmlReporter(Reporter):
    """HTML report with interactive tree."""

    name = "html"
    description = "HTML report with interactive dependency tree"
    file_extension = "html"
    writes_to_file = True

    def generate(self, data: ReportData) -> str:
        """Generate HTML content."""
        ...
```

Then register it in `woolly/reporters/__init__.py`.

## Notes

- Results should be verified manually — some packages may have different names in Fedora
- Platform-specific dependencies (like `windows-*` crates) are shown as missing but aren't needed on Linux
- The tool uses `dnf repoquery` to check Fedora packages, so it must run on a Fedora system or have access to Fedora repos
- Cache is stored in `~/.cache/woolly` and can be cleared with `woolly clear-cache`

## License

MIT License — see [LICENSE](LICENSE) for details.

## Credits

- **[Rodolfo Olivieri (@r0x0d)](https://github.com/r0x0d)** — Creator and maintainer
- **[Claude](https://claude.ai)** — AI pair programmer by [Anthropic](https://anthropic.com)

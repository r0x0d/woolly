# Woolly

Check if package dependencies are available in Fedora. Supports multiple languages including Rust and Python.

> This tool is merely a starting point for figuring out how much packaging
> effort you will need to bring a package over to Fedora.

## What does "woolly" means?

Nothing. I just liked the name.

## Supported Languages

| Language | Registry | CLI Flag |
|----------|----------|----------|
| Rust | crates.io | `--lang rust` (default) |
| Python | PyPI | `--lang python` |

More languages can be easily added by implementing the `LanguageProvider` interface.

## Installation

```bash
# Using uv
uv pip install .

# Or run directly
uv run woolly --help
```

## Usage

```bash
# Check a Rust crate (default)
woolly ripgrep

# Check a Rust crate explicitly
woolly --lang rust serde

# Check a Python package
woolly --lang python requests

# Use language aliases
woolly -l py flask
woolly -l rs tokio

# List available languages
woolly --list-languages

# Clear cache
woolly --clear-cache
```

## Example Output

### Rust

```bash
$ woolly cliclack

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
$ woolly --lang python requests

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

## Adding a New Language

To add support for a new language, create a new provider in `woolly/languages/`:

```python
# woolly/languages/go.py
from typing import Optional

import requests

from woolly.cache import DEFAULT_CACHE_TTL, read_cache, write_cache
from woolly.languages.base import Dependency, LanguageProvider, PackageInfo


class GoProvider(LanguageProvider):
    """Provider for Go modules."""
    
    # Required class attributes
    name = "go"
    display_name = "Go"
    registry_name = "Go Modules"
    fedora_provides_prefix = "golang"
    cache_namespace = "go"
    
    # Only these two methods are required to implement:
    
    def fetch_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """Fetch package info from proxy.golang.org."""
        # Your implementation here
        ...
    
    def fetch_dependencies(self, package_name: str, version: str) -> list[Dependency]:
        """Fetch dependencies from go.mod."""
        # Your implementation here
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

## Notes

Keep in mind that you may not need all of the packages to be present in Fedora.
For example, Rust crates may have platform-specific dependencies (like `windows*` crates)
that aren't used on Linux.

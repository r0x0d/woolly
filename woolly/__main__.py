"""
Woolly - Check if package dependencies are available in Fedora.

Supports multiple languages:
- Rust (crates.io)
- Python (PyPI)
"""

import sys

from woolly.commands import app


def main() -> int:
    """Main entry point."""
    app()
    return 0


if __name__ == "__main__":
    sys.exit(main())

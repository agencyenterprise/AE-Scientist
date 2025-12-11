#!/usr/bin/env python3
"""
Post-Edit Hook: Auto-format edited files

Runs prettier on JS/TS files after edits.
Configure your own formatters as needed.
"""

import json
import subprocess
import sys
from pathlib import Path

# Map file extensions to formatters
FORMATTERS = {
    ".ts": ["npx", "prettier", "--write"],
    ".tsx": ["npx", "prettier", "--write"],
    ".js": ["npx", "prettier", "--write"],
    ".jsx": ["npx", "prettier", "--write"],
    ".json": ["npx", "prettier", "--write"],
    ".md": ["npx", "prettier", "--write"],
    ".py": ["black", "--quiet"],
    ".go": ["gofmt", "-w"],
    ".rs": ["rustfmt"],
}


def format_file(file_path: str) -> bool:
    """Format a file based on its extension."""
    path = Path(file_path)
    suffix = path.suffix
    
    if suffix not in FORMATTERS:
        return True  # No formatter, that's fine
    
    formatter = FORMATTERS[suffix]
    cmd = formatter + [file_path]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Formatter not available or timed out
        return True  # Don't block on formatter issues


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    
    tool_input = data.get("tool_input", {})
    
    # Handle different tool input formats
    file_path = tool_input.get("file_path") or tool_input.get("path")
    
    if not file_path:
        sys.exit(0)
    
    # Format the file
    format_file(file_path)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

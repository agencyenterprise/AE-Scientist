#!/usr/bin/env python3
"""
Pre-Bash Hook: Block dangerous commands

Exit codes:
- 0: Allow command
- 2: Block and inform Claude
"""

import json
import sys

# Patterns that should never be executed
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    ":(){ :|:& };:",  # Fork bomb
    "> /dev/sda",
    "mkfs.",
    "dd if=/dev/zero",
    "chmod -R 777 /",
]

# Patterns that need extra scrutiny
RISKY_PATTERNS = [
    "rm -rf",
    "sudo rm",
    "DROP TABLE",
    "DROP DATABASE",
    "--force",
    "--no-preserve-root",
]


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Can't parse, allow
    
    command = data.get("tool_input", {}).get("command", "")
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern in command:
            print(json.dumps({
                "decision": "deny",
                "reason": f"🚫 Blocked: Command contains dangerous pattern '{pattern}'"
            }))
            sys.exit(0)
    
    # Warn about risky patterns (but allow)
    for pattern in RISKY_PATTERNS:
        if pattern in command:
            print(json.dumps({
                "decision": "allow",
                "reason": f"⚠️  Risky command detected: {pattern}"
            }))
            sys.exit(0)
    
    # Allow everything else
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Custom linting script to detect imports inside functions.

This script scans Python files for import statements inside function definitions,
which is against our coding standards.
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import Union


class InlineImportChecker(ast.NodeVisitor):
    """AST visitor to find imports inside functions."""

    def __init__(self) -> None:
        self.errors: list[dict[str, Union[str, int]]] = []
        self.in_function = False
        self.function_depth = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions."""
        old_in_function = self.in_function
        old_depth = self.function_depth

        self.in_function = True
        self.function_depth += 1

        self.generic_visit(node)

        self.in_function = old_in_function
        self.function_depth = old_depth

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definitions."""
        old_in_function = self.in_function
        old_depth = self.function_depth

        self.in_function = True
        self.function_depth += 1

        self.generic_visit(node)

        self.in_function = old_in_function
        self.function_depth = old_depth

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements."""
        if self.in_function:
            self.errors.append(
                {
                    "line": node.lineno,
                    "col": node.col_offset,
                    "type": "import",
                    "message": f"Import statement inside function at line {node.lineno}",
                }
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from...import statements."""
        if self.in_function:
            module = node.module or ""
            self.errors.append(
                {
                    "line": node.lineno,
                    "col": node.col_offset,
                    "type": "from_import",
                    "message": f"From-import statement inside function at line {node.lineno}: 'from {module} import ...'",
                }
            )
        self.generic_visit(node)


def check_file(file_path: Path) -> list[dict[str, Union[str, int]]]:
    """Check a single Python file for inline imports."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(file_path))
        checker = InlineImportChecker()
        checker.visit(tree)

        return checker.errors
    except SyntaxError as e:
        return [
            {
                "line": e.lineno or 0,
                "col": e.offset or 0,
                "type": "syntax_error",
                "message": f"Syntax error: {e.msg}",
            }
        ]
    except Exception as e:
        return [{"line": 0, "col": 0, "type": "error", "message": f"Error parsing file: {e}"}]


def main() -> None:
    """Main function to check all Python files."""
    parser = argparse.ArgumentParser(description="Check Python files for inline imports")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Directory or file patterns to exclude (can be used multiple times)",
    )
    parser.add_argument("files", nargs="*", help="Specific files to check")

    args = parser.parse_args()

    if args.files:
        # Check specific files passed as arguments
        files_to_check = [Path(arg) for arg in args.files]
    else:
        # Check all Python files in the current directory and subdirectories
        files_to_check = list(Path(".").rglob("*.py"))

    # Build list of patterns to exclude
    exclude_patterns = [".venv", "__pycache__", ".git", "node_modules"] + args.exclude

    total_errors = 0

    for file_path in files_to_check:
        if file_path.name == __file__.split("/")[-1]:  # Skip this script itself
            continue

        # Skip excluded directories and patterns
        if any(pattern in file_path.parts for pattern in exclude_patterns):
            continue

        errors = check_file(file_path)

        if errors:
            print(f"\n{file_path}:")
            for error in errors:
                print(f"  Line {error['line']}: {error['message']}")
                total_errors += 1

    if total_errors > 0:
        print(f"\n❌ Found {total_errors} inline import error(s)")
        sys.exit(1)
    else:
        print("✅ No inline imports found")
        sys.exit(0)


if __name__ == "__main__":
    main()

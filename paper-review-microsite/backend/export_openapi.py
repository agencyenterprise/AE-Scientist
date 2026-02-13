"""Export FastAPI OpenAPI schema to stdout."""

import json
import sys
from contextlib import redirect_stdout

# Redirect stdout to stderr during import to avoid log messages polluting the JSON output
with redirect_stdout(sys.stderr):
    from app.main import app  # noqa: E402

# Export FastAPI OpenAPI schema to stdout
if __name__ == "__main__":
    schema = app.openapi()
    json.dump(schema, sys.stdout, indent=2)
    sys.stdout.write("\n")

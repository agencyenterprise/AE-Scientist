import json
import sys

from app.main import app

# Export FastAPI OpenAPI schema to stdout
if __name__ == "__main__":
    schema = app.openapi()
    json.dump(schema, sys.stdout, indent=2)
    sys.stdout.write("\n")

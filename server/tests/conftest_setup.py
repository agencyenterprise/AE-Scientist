"""Test environment setup - imported before app modules."""

import os
import sys
from pathlib import Path

# Ensure app imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Minimal env required for app initialization in tests
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("XAI_API_KEY", "test")
os.environ.setdefault("METACOGNITION_AUTH_TOKEN", "test")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_REGION", "test")
os.environ.setdefault("AWS_S3_BUCKET_NAME", "test")

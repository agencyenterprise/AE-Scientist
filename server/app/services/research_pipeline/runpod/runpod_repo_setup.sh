#!/bin/bash

set -euo pipefail

# =============================================================================
# RunPod Code Setup Script
# =============================================================================
# Downloads and extracts the research_pipeline code from a presigned S3 URL.
#
# Required Environment Variables:
#   - CODE_TARBALL_URL: Presigned S3 URL for the code tarball
# Optional Environment Variables:
#   - PUBLIC_KEY: Public key to append to authorized_keys (for SSH access)
# =============================================================================

WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"

: "${CODE_TARBALL_URL:?ERROR: CODE_TARBALL_URL environment variable not set}"

echo "========================================"
echo "🚀 RunPod Code Setup"
echo "========================================"
echo "Workspace: ${WORKSPACE_DIR}"
echo ""

# =============================================================================
# Step 1: Ensure required tools are available
# =============================================================================
echo "Step 1: Checking required tools..."
if ! command -v curl >/dev/null 2>&1; then
  echo "  Installing curl..."
  apt-get update -y && apt-get install -y curl
else
  echo "  ✓ curl already installed"
fi

if ! command -v tar >/dev/null 2>&1; then
  echo "  Installing tar..."
  apt-get update -y && apt-get install -y tar
else
  echo "  ✓ tar already installed"
fi

# =============================================================================
# Step 2: Configure SSH (optional, for pod access)
# =============================================================================
echo ""
echo "Step 2: Configuring SSH..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh

if [ -n "${PUBLIC_KEY:-}" ]; then
  echo "  Adding public keys to authorized_keys..."
  echo "$PUBLIC_KEY" >> ~/.ssh/authorized_keys
  ssh-keygen -A
  chmod 600 ~/.ssh/authorized_keys
  service ssh start
  echo "  ✓ Public keys added to authorized_keys"
else
  echo "  ⚠️ PUBLIC_KEY not provided; skipping authorized_keys configuration."
fi

# =============================================================================
# Step 3: Download and extract code tarball
# =============================================================================
echo ""
echo "Step 3: Downloading code tarball..."
mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

TARBALL_PATH="/tmp/code_tarball.tar.gz"
curl -fsSL -o "$TARBALL_PATH" "$CODE_TARBALL_URL"
echo "  ✓ Downloaded tarball"

echo "  Extracting tarball..."
tar -xzf "$TARBALL_PATH" -C "$WORKSPACE_DIR"
rm -f "$TARBALL_PATH"
echo "  ✓ Extracted code to ${WORKSPACE_DIR}/AE-Scientist/research_pipeline"

# =============================================================================
# Step 4: Verify extraction
# =============================================================================
echo ""
echo "Step 4: Verifying code extraction..."
RESEARCH_PIPELINE_DIR="${WORKSPACE_DIR}/AE-Scientist/research_pipeline"
if [ -d "$RESEARCH_PIPELINE_DIR" ]; then
  echo "  ✓ research_pipeline directory exists"
  echo "  Contents:"
  ls -la "$RESEARCH_PIPELINE_DIR" | head -10
else
  echo "  ❌ ERROR: research_pipeline directory not found at ${RESEARCH_PIPELINE_DIR}"
  exit 1
fi

# =============================================================================
# Step 5: Done
# =============================================================================
echo ""
echo "✓ Code setup complete! Code ready at: ${RESEARCH_PIPELINE_DIR}"

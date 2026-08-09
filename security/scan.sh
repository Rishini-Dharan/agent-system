#!/bin/bash
# Security Scan Wrapper - Cross-platform (Linux/WSL/macOS)
# Usage: ./scan.sh [path] [output_dir] [docker_image]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TARGET_PATH="${1:-$PROJECT_ROOT}"
OUTPUT_DIR="${2:-$PROJECT_ROOT/reports/security}"
DOCKER_IMAGE="${3:-}"

echo "========================================="
echo "Security Scan"
echo "Target: $TARGET_PATH"
echo "Output: $OUTPUT_DIR"
echo "========================================="

# Run Python scanner
cd "$PROJECT_ROOT"
python3 security/scan.py \
    --path "$TARGET_PATH" \
    --output "$OUTPUT_DIR" \
    ${DOCKER_IMAGE:+--image "$DOCKER_IMAGE"}

EXIT_CODE=$?

echo "========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Scan completed - no critical/high findings"
else
    echo "✗ Scan completed - critical/high findings detected"
fi
echo "========================================="

exit $EXIT_CODE
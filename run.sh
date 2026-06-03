#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

IMAGE_NAME="${NIKA_IMAGE:-nika}"
IMAGE_TAG="${NIKA_TAG:-latest}"
CONTAINER_CONFIG_PATH="/home/nika/config/crtConfig.yml"
CONTAINER_SCAN_PATH="/scan"
CONTAINER_OUTPUT_DIR="/output"

echo "Nika SAST Scanner"
echo ""

# Parse --config and --path from args

CONFIG_FILE=""
SCAN_PATH=""
OUTPUT_FILE=""
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --config=*)
            CONFIG_FILE="${1#*=}"
            shift
            ;;
        --path)
            SCAN_PATH="$2"
            shift 2
            ;;
        --path=*)
            SCAN_PATH="${1#*=}"
            shift
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --output=*)
            OUTPUT_FILE="${1#*=}"
            shift
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

# Default output if not specified
if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="./report.html"
fi

OUTPUT_DIR="$(dirname "$OUTPUT_FILE")"
OUTPUT_FILENAME="$(basename "$OUTPUT_FILE")"

# Validate required args

if [[ -z "$SCAN_PATH" ]]; then
    echo -e "${RED}✗ --path is required.${NC}"
    echo "  Usage: ./run.sh --path /local/source --config config.yml [other args...]"
    exit 1
fi

if [[ -z "$CONFIG_FILE" ]]; then
    echo -e "${RED}✗ --config is required.${NC}"
    echo "  Usage: ./run.sh --path /local/source --config config.yml [other args...]"
    exit 1
fi

if [[ ! -d "$SCAN_PATH" ]]; then
    echo -e "${RED}✗ Scan path not found or not a directory: ${SCAN_PATH}${NC}"
    exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo -e "${RED}✗ Config file not found: ${CONFIG_FILE}${NC}"
    exit 1
fi

# Preflight checks

if ! command -v docker &>/dev/null; then
    echo -e "${RED}✗ Docker not found. Please install Docker.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker image ${IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo -e "${GREEN}✓ Config: ${CONFIG_FILE}${NC}"
echo -e "${GREEN}✓ Scan path: ${SCAN_PATH}${NC}"
echo -e "${GREEN}✓ Output: ${OUTPUT_FILE}${NC}"
echo ""

# Run scan

exec docker run --rm \
    -v "$(realpath "$SCAN_PATH"):${CONTAINER_SCAN_PATH}:ro" \
    -v "$(realpath "$CONFIG_FILE"):${CONTAINER_CONFIG_PATH}:ro" \
    -v "$(realpath "$OUTPUT_DIR"):${CONTAINER_OUTPUT_DIR}" \
    "${IMAGE_NAME}:${IMAGE_TAG}" \
    --path "${CONTAINER_SCAN_PATH}" \
    --output "${CONTAINER_OUTPUT_DIR}/${OUTPUT_FILENAME}" \
    ${ARGS[@]+"${ARGS[@]}"}

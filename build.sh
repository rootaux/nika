#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${NIKA_IMAGE:-nika}"
IMAGE_TAG="${NIKA_TAG:-latest}"

PLATFORM_FLAG=""
BUILD_ARGS="--build-arg OPENGREP_URL=https://github.com/opengrep/opengrep/releases/download/v1.19.0/opengrep_manylinux_x86"
if [[ "$(uname -s)" == "Darwin" ]]; then
    PLATFORM_FLAG="--platform linux/arm64"
    BUILD_ARGS="--build-arg OPENGREP_URL=https://github.com/opengrep/opengrep/releases/download/v1.19.0/opengrep_manylinux_aarch64"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building ${IMAGE_NAME}:${IMAGE_TAG} ..."
docker build $PLATFORM_FLAG $BUILD_ARGS -t "${IMAGE_NAME}:${IMAGE_TAG}" "$SCRIPT_DIR"
echo "Done: ${IMAGE_NAME}:${IMAGE_TAG}"

#!/usr/bin/env bash
# Build the shared pipeline base once:
#   codingbench-base/ubuntu:24.04
# FROM official ubuntu:24.04 plus the pinned toolchain in Dockerfile.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TAG="${1:-codingbench-base/ubuntu:24.04}"
FROM_IMAGE="${FROM_IMAGE:-ubuntu:24.04}"
PLATFORM="${CBRUN_PLATFORM:-${DOCKER_DEFAULT_PLATFORM:-linux/amd64}}"
if [[ "$PLATFORM" != linux/amd64 ]]; then
    echo 'The bundled toolchain requires linux/amd64.' >&2
    exit 2
fi

docker pull --platform "$PLATFORM" "${FROM_IMAGE}"
docker build \
    --platform "$PLATFORM" \
    --build-arg "FROM_IMAGE=${FROM_IMAGE}" \
    -t "${TAG}" \
    "${ROOT}"
echo "built ${TAG}"

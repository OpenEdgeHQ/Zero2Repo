#!/usr/bin/env bash
# Build the shared pipeline base once:
#   codingbench-base/ubuntu:24.04
# FROM official ubuntu:24.04 plus the pinned toolchain in Dockerfile.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TAG="${1:-codingbench-base/ubuntu:24.04}"
FROM_IMAGE="${FROM_IMAGE:-ubuntu:24.04}"

docker pull "${FROM_IMAGE}"
docker build \
    --build-arg "FROM_IMAGE=${FROM_IMAGE}" \
    -t "${TAG}" \
    "${ROOT}"
echo "built ${TAG}"

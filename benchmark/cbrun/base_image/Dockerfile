# Shared pipeline base used by recipe.lock as codingbench-base/ubuntu:24.04.
# Starts from official Ubuntu, then installs the toolchain hidden tests and
# per-case install_command assume (Python, pytest, compilers, Node, Miniconda).
# Not a retag of ubuntu:24.04.
#
# Official download URLs only (no regional mirrors). Node is checksum-pinned.
# Miniconda uses the official "latest" installer, matching the original recipe.

ARG FROM_IMAGE=ubuntu:24.04
FROM ${FROM_IMAGE}

ARG NODE_VERSION=20.18.1
ARG NODE_TARBALL_SHA256=c6fa75c841cbffac851678a472f2a5bd612fff8308ef39236190e1f8dbb0e567
ARG VITEST_VERSION=3.2.6
ARG TYPESCRIPT_VERSION=5.9.3
ARG TYPES_NODE_VERSION=20
ARG PYTEST_VERSION=9.0.3
ARG MINICONDA_INSTALLER=Miniconda3-latest-Linux-x86_64.sh

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_NO_CACHE_DIR=1

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        git \
        curl \
        wget \
        ca-certificates \
        unzip \
        xz-utils \
        python3 \
        python3-pip \
        python3-venv; \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    python3 -m pip install --no-cache-dir --break-system-packages \
        "pytest==${PYTEST_VERSION}"

RUN set -eux; \
    curl -fsSL \
        "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
        -o /tmp/node.tar.xz; \
    echo "${NODE_TARBALL_SHA256}  /tmp/node.tar.xz" | sha256sum -c -; \
    tar -xJ -C /usr/local --strip-components=1 -f /tmp/node.tar.xz; \
    rm -f /tmp/node.tar.xz; \
    npm install -g \
        "vitest@${VITEST_VERSION}" \
        "typescript@${TYPESCRIPT_VERSION}" \
        "@types/node@${TYPES_NODE_VERSION}"

RUN set -eux; \
    curl -fsSL \
        "https://repo.anaconda.com/miniconda/${MINICONDA_INSTALLER}" \
        -o /tmp/miniconda.sh; \
    bash /tmp/miniconda.sh -b -p /opt/conda; \
    rm -f /tmp/miniconda.sh; \
    CONDA_PLUGINS_AUTO_ACCEPT_TOS=1 \
        /opt/conda/bin/conda install -y "pytest=${PYTEST_VERSION}"; \
    /opt/conda/bin/conda clean -afy; \
    ln -sf /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh

ENV PATH=/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN python3 --version \
    && pytest --version \
    && conda --version \
    && node --version \
    && npm --version \
    && vitest --version \
    && tsc --version

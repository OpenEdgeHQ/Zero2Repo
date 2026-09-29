# Pinned OpenHands CLI for cbrun agent images.
# Case deliverable images ship Python 3.13; openhands==1.16.0 requires 3.12.
# Build once, then COPY --from this image in each :agent-openhands layer.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"
RUN uv python install 3.12 \
    && uv tool install 'openhands==1.16.0' --python 3.12 \
    && /root/.local/bin/openhands --version

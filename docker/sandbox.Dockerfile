FROM python:3.11-slim

# The verifier runs pytest; patch validation uses git apply inside the sandbox.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends git \
    && pip install --no-cache-dir pytest==8.4.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

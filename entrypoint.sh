#!/bin/sh
set -e

ENGINE="skills/last30days/scripts/last30days.py"

# Build --search flag from SOURCES env var if set.
SEARCH_FLAG=""
if [ -n "${SOURCES}" ]; then
    SEARCH_FLAG="--search=${SOURCES}"
fi

# Research on startup: run the engine if a topic is configured.
if [ -n "${RESEARCH_TOPIC}" ]; then
    echo "[entrypoint] Running research: ${RESEARCH_TOPIC}"

    # Save the agent-friendly HTML report.
    # shellcheck disable=SC2086
    python3 "${ENGINE}" \
        "${RESEARCH_TOPIC}" \
        --emit=html \
        --save-dir=/data \
        ${SEARCH_FLAG}

    # Also save raw JSON evidence (threads, stories, items with full metadata).
    # shellcheck disable=SC2086
    python3 "${ENGINE}" \
        "${RESEARCH_TOPIC}" \
        --emit=json \
        --json-profile=raw \
        --save-dir=/data \
        ${SEARCH_FLAG}

    echo "[entrypoint] Research complete"
fi

# Start the web server.
echo "[entrypoint] Starting web server on port 8080"
exec python3 scripts/serve.py /data --port 8080
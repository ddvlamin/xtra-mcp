#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-qwen2.5:3b}"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

echo "==> Target Model: $MODEL"
echo "==> Ollama Host: $OLLAMA_HOST"

# 1. Check dependencies and install Ollama CLI if missing
if ! command -v ollama >/dev/null 2>&1; then
    echo "==> Ollama CLI not found. Checking dependencies..."
    if ! command -v zstd >/dev/null 2>&1; then
        echo "==> Installing zstd..."
        if command -v sudo >/dev/null 2>&1; then
            sudo apt-get update && sudo apt-get install -y zstd
        elif command -v apt-get >/dev/null 2>&1; then
            apt-get update && apt-get install -y zstd
        fi
    fi

    echo "==> Installing Ollama..."
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL https://ollama.com/install.sh | sh
    else
        echo "Error: curl is required to install Ollama." >&2
        exit 1
    fi
fi

# 2. Check if Ollama server is running
if ! curl -s "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    echo "==> Starting Ollama server in background..."
    ollama serve >/tmp/ollama_serve.log 2>&1 &
    OLLAMA_PID=$!
    echo "==> Ollama server started with PID $OLLAMA_PID (log: /tmp/ollama_serve.log)"

    # Wait for server to become responsive
    echo "==> Waiting for Ollama server to be ready..."
    MAX_RETRIES=30
    COUNT=0
    until curl -s "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; do
        sleep 1
        COUNT=$((COUNT + 1))
        if [ "$COUNT" -ge "$MAX_RETRIES" ]; then
            echo "Error: Ollama server failed to start within $MAX_RETRIES seconds." >&2
            cat /tmp/ollama_serve.log >&2
            exit 1
        fi
    done
    echo "==> Ollama server is up and running."
else
    echo "==> Ollama server is already running."
fi

# 3. Pull / Download the model
echo "==> Pulling model: $MODEL..."
ollama pull "$MODEL"

# 4. Verify / Preload model
echo "==> Verifying model $MODEL..."
ollama run "$MODEL" "ready" >/dev/null 2>&1 || true

echo "==> Success: Model '$MODEL' is ready at $OLLAMA_HOST"

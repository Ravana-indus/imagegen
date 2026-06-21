#!/usr/bin/env bash

# Export the fork safety workaround (specifically for macOS local dev, harmless on Linux)
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Start the RQ worker in the background
echo "Starting background worker..."
uv run python -m app.worker &

# Start the FastAPI server in the foreground
echo "Starting web server..."
uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port $PORT

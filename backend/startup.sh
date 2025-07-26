#!/bin/bash
set -e

echo "=== Tenant Optimizer Azure Startup Script ==="
echo "Startup script: starting at $(date)"
echo "Current working directory: $(pwd)"
echo "Contents of /home/site/wwwroot/:"
ls -la /home/site/wwwroot/ 2>/dev/null || echo "Directory /home/site/wwwroot/ not found"

# Upgrade pip for better package management
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies from the correct backend path
REQUIREMENTS_PATH="/home/site/wwwroot/backend/requirements.txt"
echo "Installing dependencies from: $REQUIREMENTS_PATH"
if [ -f "$REQUIREMENTS_PATH" ]; then
    pip install -r "$REQUIREMENTS_PATH"
    echo "Startup script: pip install finished at $(date)"
else
    echo "ERROR: Requirements file not found at $REQUIREMENTS_PATH"
    echo "Available files in /home/site/wwwroot/backend/:"
    ls -la /home/site/wwwroot/backend/ 2>/dev/null || echo "Backend directory not found"
    exit 1
fi

# Set working directory and start the FastAPI app with gunicorn
BACKEND_DIR="/home/site/wwwroot/backend"
echo "Starting gunicorn with working directory: $BACKEND_DIR"
echo "Using port: ${PORT:-8000}"

# Use dynamic port for Azure compatibility and set correct working directory
exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:${PORT:-8000} --chdir "$BACKEND_DIR"
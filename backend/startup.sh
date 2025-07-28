#!/bin/bash
set -e

echo "=== Tenant Optimizer Startup Script ==="
echo "Starting at: $(date)"
echo "Working directory: $(pwd)"
echo "Python version: $(python3 --version)"

# Upgrade pip first
echo "Upgrading pip..."
python3 -m pip install --upgrade pip

# Install dependencies
echo "Installing Python dependencies..."
python3 -m pip install -r /home/site/wwwroot/requirements.txt

echo "Dependencies installed successfully at: $(date)"

# List installed packages for debugging
echo "Installed packages:"
python3 -m pip list | grep -E "(fastapi|uvicorn|gunicorn|httpx|jwt|openai)"

# Test import of main module
echo "Testing main module import..."
python3 -c "import main; print('Main module imported successfully')"

# Set environment variables
export PORT=${PORT:-8000}
echo "Starting server on port: $PORT"

# Start the application
echo "Starting Gunicorn with Uvicorn worker..."
exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:${PORT} --timeout 120 --workers 1 --log-level info
#!/bin/bash
set -e

echo "=== Tenant Optimizer Startup ==="
echo "Starting at: $(date)"

# Install dependencies
echo "Installing dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r /home/site/wwwroot/requirements.txt

echo "Dependencies installed at: $(date)"

# Start the application
export PORT=${PORT:-8000}
echo "Starting server on port: $PORT"

exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:${PORT} --timeout 120 --log-level info
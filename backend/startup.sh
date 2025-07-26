#!/bin/bash
set -e

echo "Startup script: starting at $(date)"
pip install --upgrade pip
pip install -r /home/site/wwwroot/requirements.txt
echo "Startup script: pip install finished at $(date)"

# Use dynamic port for Azure compatibility
exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:${PORT:-8000}
#!/bin/bash
set -e

# Always (re)install requirements
pip install --upgrade pip
pip install -r /home/site/wwwroot/requirements.txt

# Start your FastAPI app using Gunicorn & Uvicorn worker
exec gunicorn main:app -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000
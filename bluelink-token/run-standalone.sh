#!/bin/bash
# Standalone startup script for Docker (without Home Assistant)

echo "Starting Bluelink Token Generator (standalone)..."
echo "Brand: ${BRAND:-auto}"
echo "Web UI available at port 9876"

source /opt/venv/bin/activate
exec gunicorn --bind 0.0.0.0:9876 --workers 1 --threads 4 --timeout 300 web:app

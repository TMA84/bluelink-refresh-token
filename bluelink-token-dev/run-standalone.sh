#!/command/with-contenv bash
# Standalone startup script for Docker (without Home Assistant)

echo "Starting Bluelink Token Generator (standalone)..."
echo "Web UI available at port 9877"

source /opt/venv/bin/activate
exec gunicorn --bind 0.0.0.0:9877 --workers 1 --threads 4 --timeout 300 web:app

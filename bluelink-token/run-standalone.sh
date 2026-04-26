#!/command/with-contenv bash
# Standalone startup script for Docker (without Home Assistant)
# Uses with-contenv to inherit container environment variables through s6-overlay

echo "Starting Bluelink Token Generator (standalone)..."
echo "Brand: ${BRAND:-auto}"
if [ -n "$BLUELINK_USERNAME" ]; then
    echo "Username configured - auto-login enabled"
fi
echo "Web UI available at port 9876"

source /opt/venv/bin/activate
exec gunicorn --bind 0.0.0.0:9876 --workers 1 --threads 4 --timeout 300 web:app

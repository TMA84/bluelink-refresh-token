#!/usr/bin/with-contenv bashio

BRAND=$(bashio::config 'brand')
USERNAME=$(bashio::config 'username')
PASSWORD=$(bashio::config 'password')
export BRAND
export BLUELINK_USERNAME="$USERNAME"
export BLUELINK_PASSWORD="$PASSWORD"
export DISPLAY=:99

bashio::log.info "Starting Bluelink Token Generator..."
bashio::log.info "Brand: ${BRAND}"
if [ -n "$USERNAME" ]; then
    bashio::log.info "Username configured - auto-fill enabled"
fi

# Start virtual framebuffer
bashio::log.info "Starting Xvfb..."
Xvfb :99 -screen 0 1280x800x24 -ac &
sleep 1

# Start window manager
openbox &
sleep 1

# Start VNC server
bashio::log.info "Starting VNC server..."
x11vnc -display :99 -forever -nopw -shared -rfbport 5900 &
sleep 1

# Start noVNC web client
bashio::log.info "Starting noVNC on port 6080..."
websockify --web /usr/share/novnc 6080 localhost:5900 &
sleep 1

bashio::log.info "noVNC available at port 6080"
bashio::log.info "Web UI available at port 9876"

# Activate virtual environment and run web server
source /opt/venv/bin/activate
exec gunicorn --bind 0.0.0.0:9876 --workers 1 --threads 4 --timeout 300 web:app

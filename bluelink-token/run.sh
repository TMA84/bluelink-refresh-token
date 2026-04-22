#!/usr/bin/with-contenv bashio

BRAND=$(bashio::config 'brand')
USERNAME=""
PASSWORD=""
EVCC_URL=""
EVCC_PASSWORD=""

if bashio::config.has_value 'username'; then
    USERNAME=$(bashio::config 'username')
fi
if bashio::config.has_value 'password'; then
    PASSWORD=$(bashio::config 'password')
fi
if bashio::config.has_value 'country'; then
    COUNTRY=$(bashio::config 'country')
    export COUNTRY
fi
if bashio::config.has_value 'evcc_url'; then
    EVCC_URL=$(bashio::config 'evcc_url')
fi
if bashio::config.has_value 'evcc_password'; then
    EVCC_PASSWORD=$(bashio::config 'evcc_password')
fi
export BRAND
export BLUELINK_USERNAME="$USERNAME"
export BLUELINK_PASSWORD="$PASSWORD"
export EVCC_URL
export EVCC_PASSWORD
export DISPLAY=:99
export DBUS_SESSION_BUS_ADDRESS=/dev/null

bashio::log.info "Starting Bluelink Token Generator..."
bashio::log.info "Brand: ${BRAND}"
if [ -n "$USERNAME" ]; then
    bashio::log.info "Username configured - auto-fill enabled"
fi

# Start virtual framebuffer
bashio::log.info "Starting Xvfb..."
Xvfb :99 -screen 0 1280x800x24 -ac &
sleep 1

# Start window manager (no decorations)
mkdir -p /root/.config/openbox
cat > /root/.config/openbox/rc.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <applications>
    <application class="*">
      <decor>no</decor>
      <maximized>yes</maximized>
    </application>
  </applications>
</openbox_config>
EOF
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

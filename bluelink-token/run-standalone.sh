#!/bin/bash
# Standalone startup script for Docker (without Home Assistant)

export DISPLAY=:99
export DBUS_SESSION_BUS_ADDRESS=/dev/null

echo "Starting Bluelink Token Generator (standalone)..."
echo "Brand: ${BRAND:-auto}"

# Start virtual framebuffer
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1280x800x24 -ac &
sleep 1

# Start window manager (no decorations, maximized)
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
echo "Starting VNC server..."
x11vnc -display :99 -forever -nopw -shared -rfbport 5900 &
sleep 1

# Start noVNC web client
echo "Starting noVNC on port 6080..."
websockify --web /usr/share/novnc 6080 localhost:5900 &
sleep 1

echo "noVNC available at port 6080"
echo "Web UI available at port 9876"

# Activate virtual environment and run web server
source /opt/venv/bin/activate
exec gunicorn --bind 0.0.0.0:9876 --workers 1 --threads 4 --timeout 300 web:app

#!/usr/bin/with-contenv bashio

EVCC_URL=""
EVCC_PASSWORD=""
API_TOKEN=""

if bashio::config.has_value 'country'; then
    export COUNTRY=$(bashio::config 'country')
fi
if bashio::config.has_value 'evcc_url'; then
    EVCC_URL=$(bashio::config 'evcc_url')
fi
if bashio::config.has_value 'evcc_password'; then
    EVCC_PASSWORD=$(bashio::config 'evcc_password')
fi
if bashio::config.has_value 'api_token'; then
    API_TOKEN=$(bashio::config 'api_token')
fi

# Build vehicles JSON from config
VEHICLES_JSON=$(bashio::config 'vehicles')
export VEHICLES_JSON
export EVCC_URL
export EVCC_PASSWORD
export API_TOKEN

bashio::log.info "Starting Bluelink Token Generator..."
vehicle_count=$(echo "$VEHICLES_JSON" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read())))" 2>/dev/null || echo "0")
bashio::log.info "Vehicles configured: ${vehicle_count}"
bashio::log.info "Web UI available at port 9877"

source /opt/venv/bin/activate
exec gunicorn --bind 0.0.0.0:9877 --workers 1 --threads 4 --timeout 300 web:app

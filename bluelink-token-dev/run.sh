#!/usr/bin/with-contenv bashio

EVCC_URL=""
EVCC_PASSWORD=""
API_TOKEN=""
HA_URL=""
HA_TOKEN=""
HA_KIA_UVO_TRANSFER=""
HA_KIA_UVO_PIN=""

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
if bashio::config.has_value 'ha_url'; then
    HA_URL=$(bashio::config 'ha_url')
fi
if bashio::config.has_value 'ha_token'; then
    HA_TOKEN=$(bashio::config 'ha_token')
fi
if bashio::config.has_value 'ha_kia_uvo_transfer'; then
    HA_KIA_UVO_TRANSFER=$(bashio::config 'ha_kia_uvo_transfer')
fi
if bashio::config.has_value 'ha_kia_uvo_pin'; then
    HA_KIA_UVO_PIN=$(bashio::config 'ha_kia_uvo_pin')
fi

# Build vehicles JSON from config
VEHICLES_JSON=$(bashio::config 'vehicles')
export VEHICLES_JSON
export EVCC_URL
export EVCC_PASSWORD
export API_TOKEN
export HA_URL
export HA_TOKEN
export HA_KIA_UVO_TRANSFER
export HA_KIA_UVO_PIN

bashio::log.info "Starting Bluelink Token Generator..."
vehicle_count=$(echo "$VEHICLES_JSON" | python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
if isinstance(data, list):
    print(len([v for v in data if isinstance(v, dict) and 'brand' in v]))
elif isinstance(data, dict) and 'brand' in data:
    print(1)
else:
    print(0)
" 2>/dev/null || echo "0")
bashio::log.info "Vehicles configured: ${vehicle_count}"
bashio::log.info "Web UI available at port 9877"

source /opt/venv/bin/activate
exec gunicorn --bind 0.0.0.0:9877 --workers 1 --threads 4 --timeout 300 web:app

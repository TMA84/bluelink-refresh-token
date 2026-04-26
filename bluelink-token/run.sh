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

bashio::log.info "Starting Bluelink Token Generator..."
bashio::log.info "Brand: ${BRAND}"
if [ -n "$USERNAME" ]; then
    bashio::log.info "Username configured - auto-login enabled"
fi
bashio::log.info "Web UI available at port 9876"

source /opt/venv/bin/activate
exec gunicorn --bind 0.0.0.0:9876 --workers 1 --threads 4 --timeout 300 web:app

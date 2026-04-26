FROM ghcr.io/home-assistant/base:latest

LABEL \
    org.opencontainers.image.title="Bluelink Token Generator" \
    org.opencontainers.image.description="Generate Hyundai/Kia Bluelink refresh tokens for evcc and Home Assistant" \
    org.opencontainers.image.source="https://github.com/TMA84/bluelink-refresh-token" \
    org.opencontainers.image.licenses="MIT" \
    io.hass.name="Bluelink Token Generator" \
    io.hass.description="Generate Hyundai/Kia Bluelink refresh tokens" \
    io.hass.type="addon" \
    io.hass.url="https://github.com/TMA84/bluelink-refresh-token"

RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip3 install --no-cache-dir requests flask gunicorn curl_cffi pycryptodome

WORKDIR /app

COPY web.py /app/
COPY config.yaml /app/
COPY run.sh /
COPY run-standalone.sh /
RUN chmod a+x /run.sh /run-standalone.sh

EXPOSE 9876

CMD [ "/run.sh" ]

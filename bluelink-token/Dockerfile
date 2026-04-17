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

# Install dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    chromium \
    chromium-chromedriver \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    openbox \
    xdotool \
    font-noto \
    ttf-freefont \
    dbus \
    bash

# Create virtual environment and install dependencies
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip3 install --no-cache-dir selenium requests flask gunicorn

# Copy addon files
WORKDIR /app

# Verify chromium and chromedriver are installed
RUN ls -la /usr/bin/chromium* /usr/lib/chromium/chromedriver 2>/dev/null || true
RUN ln -sf /usr/lib/chromium/chromedriver /usr/bin/chromedriver 2>/dev/null || true

COPY web.py /app/
COPY run.sh /
COPY run-standalone.sh /
RUN chmod a+x /run.sh /run-standalone.sh

EXPOSE 9876 6080

CMD [ "/run.sh" ]

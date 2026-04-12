ARG BUILD_FROM
FROM $BUILD_FROM

ARG CACHEBUST=1

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
RUN pip3 install --no-cache-dir selenium requests flask

# Copy addon files
WORKDIR /app

# Verify chromium and chromedriver are installed
RUN ls -la /usr/bin/chromium* /usr/lib/chromium/chromedriver 2>/dev/null || true
RUN ln -sf /usr/lib/chromium/chromedriver /usr/bin/chromedriver 2>/dev/null || true

COPY web.py /app/
COPY run.sh /
RUN chmod a+x /run.sh

EXPOSE 9876 6080

CMD [ "/run.sh" ]

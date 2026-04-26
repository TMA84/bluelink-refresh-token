# Docker / Podman Setup

## Docker Compose (recommended)

```yaml
services:
  bluelink-token:
    image: ghcr.io/tma84/bluelink-token:latest
    container_name: bluelink-token
    ports:
      - "9876:9876"
    environment:
      - BRAND=eu_kia              # or eu_hyundai
      - BLUELINK_USERNAME=your@email.com
      - BLUELINK_PASSWORD=yourpassword
      - EVCC_URL=http://evcc:7070 # optional
      - EVCC_PASSWORD=            # optional
    command: ["/run-standalone.sh"]
    restart: unless-stopped
```

```bash
docker compose up -d
```

Then open `http://localhost:9876`.

## Docker Run

```bash
docker run -d \
  --name bluelink-token \
  -p 9876:9876 \
  -e BRAND=eu_kia \
  -e BLUELINK_USERNAME=your@email.com \
  -e BLUELINK_PASSWORD=yourpassword \
  ghcr.io/tma84/bluelink-token:latest \
  /run-standalone.sh
```

Replace `docker` with `podman` if using Podman.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BRAND` | `auto`, `eu_kia`, or `eu_hyundai` | `auto` |
| `BLUELINK_USERNAME` | Bluelink email/username | |
| `BLUELINK_PASSWORD` | Bluelink password (8-20 characters) | |
| `EVCC_URL` | evcc URL for automatic token transfer | |
| `EVCC_PASSWORD` | evcc admin password | |
| `COUNTRY` | Country code for EU Hyundai | `DE` |

> **Password requirements:** 8–20 characters, at least one uppercase letter, one lowercase letter, one digit, and one special character.

## How it works

When credentials are set via environment variables, the token is generated automatically on container start:

1. Headless login via `curl_cffi` (Android TLS fingerprint)
2. RSA password encryption (same as the official app)
3. Token exchange → refresh + access token
4. If `EVCC_URL` is set → token is transferred to evcc and evcc is restarted

No browser, no manual interaction needed.

## Web UI

Open `http://localhost:9876` to:
- Generate a token manually (enter credentials + click "Generate Token")
- View the current token
- Transfer the token to evcc
- Verify the token

## Multiple Vehicles (Kia + Hyundai)

Run two containers with different ports:

```yaml
services:
  bluelink-kia:
    image: ghcr.io/tma84/bluelink-token:latest
    ports: ["9876:9876"]
    environment:
      - BRAND=eu_kia
      - BLUELINK_USERNAME=kia@email.com
      - BLUELINK_PASSWORD=kiapass
      - EVCC_URL=http://evcc:7070
      - EVCC_PASSWORD=adminpass
    command: ["/run-standalone.sh"]

  bluelink-hyundai:
    image: ghcr.io/tma84/bluelink-token:latest
    ports: ["9877:9876"]
    environment:
      - BRAND=eu_hyundai
      - BLUELINK_USERNAME=hyundai@email.com
      - BLUELINK_PASSWORD=hyundaipass
      - EVCC_URL=http://evcc:7070
      - EVCC_PASSWORD=adminpass
    command: ["/run-standalone.sh"]
```

## Supported Architectures

The image is a multi-arch manifest:
- `amd64` — Intel/AMD (x86_64)
- `aarch64` — Apple Silicon, Raspberry Pi, ODROID

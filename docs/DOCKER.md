# Docker / Podman Setup

This is the recommended method if you:
- Run Home Assistant as a Docker container (no Add-on store available)
- Use a NAS (Synology, QNAP, Unraid, TrueNAS)
- Have any Linux server with Docker installed

The container runs independently — it does not need to be installed "inside" Home Assistant.

## NAS Quick Start (Synology, QNAP, Unraid)

### Synology (Container Manager / Docker)

1. Open **Container Manager** (or Docker package on older DSM)
2. Go to **Registry** → search for `ghcr.io/tma84/bluelink-token`
3. Download the `latest` tag
4. Create a container with:
   - **Port:** Local port `9876` → Container port `9876`
   - **Environment variables:** see [Environment Variables](#environment-variables) below
   - **Command:** `/run-standalone.sh`
5. Start the container and open `http://your-nas-ip:9876`

### QNAP (Container Station)

1. Open **Container Station**
2. Click **Create** → **Create Application** (or use Docker CLI via SSH)
3. Use the Docker Compose example below
4. Access the Web UI at `http://your-nas-ip:9876`

### Unraid

1. Open a terminal and run the `docker run` command below
2. Or add via **Docker** tab → **Add Container** with the image `ghcr.io/tma84/bluelink-token:latest`

## Docker Compose (recommended)

```yaml
services:
  bluelink-token:
    image: ghcr.io/tma84/bluelink-token:latest
    container_name: bluelink-token
    ports:
      - "9876:9876"
    volumes:
      - bluelink-data:/data    # persists token expiry info across restarts
    environment:
      - BRAND=eu_kia              # or eu_hyundai
      - BLUELINK_USERNAME=your@email.com
      - BLUELINK_PASSWORD=yourpassword
      - EVCC_URL=http://evcc:7070 # optional
      - EVCC_PASSWORD=            # optional
    command: ["/run-standalone.sh"]
    restart: unless-stopped

volumes:
  bluelink-data:
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
| `BRAND` | `auto`, `eu_kia`, or `eu_hyundai` (single vehicle) | `auto` |
| `BLUELINK_USERNAME` | Bluelink email/username (single vehicle) | |
| `BLUELINK_PASSWORD` | Bluelink password (single vehicle, 8-20 characters) | |
| `VEHICLES_JSON` | JSON array of vehicles (multi-vehicle, overrides BRAND/USERNAME/PASSWORD) | |
| `EVCC_URL` | evcc URL for automatic token transfer | |
| `EVCC_PASSWORD` | evcc admin password | |
| `COUNTRY` | Country code for EU Hyundai | `DE` |
| `WEBHOOK_URL` | URL to receive POST notifications on token events | |
| `RENEWAL_INTERVAL` | Auto-renewal check interval in seconds | `86400` (24h) |
| `API_TOKEN` | Bearer token to secure API endpoints | |

### Multi-Vehicle via VEHICLES_JSON

```bash
docker run -d --name bluelink-token -p 9876:9876 \
  -e 'VEHICLES_JSON=[{"brand":"eu_kia","username":"kia@email.com","password":"kiapass"},{"brand":"eu_hyundai","username":"hyundai@email.com","password":"hyundaipass"}]' \
  -e EVCC_URL=http://evcc:7070 \
  -v bluelink-data:/data \
  ghcr.io/tma84/bluelink-token:latest /run-standalone.sh
```

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

## Automatic Token Renewal

The container has **built-in auto-renewal**: it checks token expiry every 24 hours and automatically renews tokens that are about to expire (<14 days remaining). No cron jobs or external automation needed — just keep the container running.

You can customize the check interval via the `RENEWAL_INTERVAL` environment variable (in seconds, default: 86400 = 24h).

### Alternative: External triggers

If you prefer explicit control, you can also trigger renewal externally:

#### Cron-based API call

```bash
# Crontab: check and renew tokens once per week
0 3 * * 1 curl -s -X POST http://localhost:9876/api/tokens > /dev/null
```

#### Container restart

```bash
# Crontab: restart container once per week (triggers expiry check on start)
0 3 * * 1 docker restart bluelink-token
```

#### With API_TOKEN (secured)

```bash
0 3 * * 1 curl -s -X POST http://localhost:9876/api/tokens -H "Authorization: Bearer my-secret-token" > /dev/null
```

> **Note:** Each token generation is a full login at Kia/Hyundai — too many logins could trigger rate limiting. The 14-day threshold provides enough buffer for retries if a login fails.

## Webhooks

Set `WEBHOOK_URL` to receive HTTP POST notifications when tokens are generated or fail:

```bash
docker run -d --name bluelink-token -p 9876:9876 \
  -e BRAND=eu_kia \
  -e BLUELINK_USERNAME=your@email.com \
  -e BLUELINK_PASSWORD=yourpassword \
  -e WEBHOOK_URL=http://your-server/webhook \
  ghcr.io/tma84/bluelink-token:latest /run-standalone.sh
```

Webhook payload:
```json
{
  "event": "token_generated",
  "timestamp": "2026-05-03T12:00:00+00:00",
  "data": {
    "vehicles": [{"brand": "eu_kia", "username": "user@example.com"}]
  }
}
```

Events: `token_generated`, `token_failed`

## Healthcheck

The container exposes a healthcheck endpoint:

```bash
curl http://localhost:9876/health
```

```json
{"status": "ok", "version": "6.5.0", "vehicles_configured": 1}
```

Use this in Docker Compose:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:9876/health"]
  interval: 60s
  timeout: 5s
  retries: 3
```

## Supported Architectures

The image is a multi-arch manifest:
- `amd64` — Intel/AMD (x86_64)
- `aarch64` — Apple Silicon, Raspberry Pi, ODROID

## Related Documentation

- [API Documentation](API.md) — REST API for programmatic token retrieval
- [evcc Integration](EVCC.md) — Automatic token transfer to evcc
- [kia_uvo Integration](KIA_UVO.md) — Automatic token transfer to kia_uvo in Home Assistant
- [Home Assistant Setup](HOME_ASSISTANT.md) — Add-on installation for HAOS/Supervised

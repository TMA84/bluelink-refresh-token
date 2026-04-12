# Bluelink Refresh Token

Home Assistant addon to generate Hyundai/Kia Bluelink refresh tokens for [evcc](https://evcc.io) and Home Assistant integrations.

## How it works

This addon runs a Chromium browser inside the container with the correct mobile user-agent required by the Bluelink OAuth flow. You interact with the browser through an embedded noVNC viewer to complete the login. The addon then automatically extracts the refresh token.

1. Configure your brand (Hyundai/Kia) and optionally your credentials
2. Click "Start token generation"
3. Sign in via the embedded browser (credentials are auto-filled if configured)
4. The refresh token is extracted and displayed
5. Use the "Verify token" button to confirm it works

## Installation

Add this repository to your Home Assistant addon store:

```
https://github.com/TMA84/bluelink-refresh-token
```

Settings → Add-ons → Add-on Store → three dots menu → Repositories → paste the URL above.

## Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `brand` | Vehicle brand: `hyundai` or `kia` | `hyundai` |
| `username` | Bluelink email/username (optional, for auto-fill) | |
| `password` | Bluelink password (optional, for auto-fill) | |

## Ports

| Port | Description |
|------|-------------|
| 9876 | Web UI |
| 6080 | noVNC (remote browser) |

## Usage

The generated refresh token is valid for **180 days**. Use it as the password together with your regular username when configuring:

- [evcc](https://docs.evcc.io/docs/devices/vehicles#hyundai--kia) vehicle integration
- [Home Assistant Kia/Hyundai integration](https://github.com/Hyundai-Kia-Connect/kia_uvo)

## Standalone mit Docker (ohne Home Assistant)

Falls du kein Home Assistant nutzt, kannst du den Container auch direkt mit Docker starten:

```bash
docker run -d \
  --name bluelink-token \
  -p 9876:9876 \
  -p 6080:6080 \
  -e BRAND=hyundai \
  -e BLUELINK_USERNAME=deine@email.de \
  -e BLUELINK_PASSWORD=deinpasswort \
  ghcr.io/tma84/bluelink-token-amd64:latest
```

Für ARM-Geräte (z.B. Raspberry Pi) stattdessen `bluelink-token-aarch64` verwenden:

```bash
docker run -d \
  --name bluelink-token \
  -p 9876:9876 \
  -p 6080:6080 \
  -e BRAND=kia \
  -e BLUELINK_USERNAME=deine@email.de \
  -e BLUELINK_PASSWORD=deinpasswort \
  ghcr.io/tma84/bluelink-token-aarch64:latest
```

Danach erreichbar unter `http://localhost:9876`. Username und Passwort sind optional — ohne werden die Felder nicht automatisch ausgefüllt.

Verfügbare Architekturen: `amd64`, `aarch64`, `armv7`, `armhf`, `i386`.

## Credits

Based on [bluelink_refresh_token](https://github.com/RustyDust/bluelink_refresh_token) by RustyDust.

## License

MIT

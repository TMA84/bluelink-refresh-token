<p align="center">
  <img src="bluelink-token/logo.png" alt="Bluelink Token Generator" width="200">
</p>

<h1 align="center">Bluelink Token Generator</h1>

<p align="center">
  Generate Hyundai/Kia Bluelink refresh tokens for
  <a href="https://evcc.io">evcc</a> and
  <a href="https://www.home-assistant.io/">Home Assistant</a> —
  fully automatic, no browser interaction needed.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/aarch64-yes-green.svg" alt="Supports aarch64">
  <img src="https://img.shields.io/badge/amd64-yes-green.svg" alt="Supports amd64">
  <img src="https://img.shields.io/github/v/release/TMA84/bluelink-refresh-token" alt="GitHub Release">
  <img src="https://img.shields.io/github/license/TMA84/bluelink-refresh-token" alt="License">
</p>

<p align="center">
  <a href="https://buymeacoffee.com/tobiasmalct"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy me a coffee" width="217"></a>
</p>

---

## About

Generates Bluelink refresh tokens for EU Kia and EU Hyundai vehicles. Fully **headless** — no browser, no CAPTCHA, no manual interaction. Configure your credentials and the token is generated automatically.

Developed by reverse engineering the official Kia Connect App. Uses `curl_cffi` to impersonate an Android Chrome TLS fingerprint.

### Features

- **Fully headless** — no browser, no Chromium, lightweight container
- **Multi-vehicle** — configure multiple Kia + Hyundai vehicles at once
- **Auto-renewal** — checks token expiry daily and renews automatically when needed
- **Retry logic** — transient login failures are retried automatically
- **Token expiry check** — only renews when tokens are about to expire (<14 days)
- **evcc integration** — transfers tokens to evcc and restarts automatically
- **HA Ingress** — Web UI accessible directly from the Home Assistant sidebar
- **Simple Web UI** — add vehicles dynamically, click "Generate All Tokens"
- **Dark mode** — automatic dark/light theme based on system preference
- **Webhooks** — receive HTTP notifications on token events
- **Healthcheck endpoint** — `/health` for Docker orchestrators
- Home Assistant token expiry sensor + persistent notifications
- **Standalone apps** — native downloads for Windows (.exe), macOS (.dmg) and Linux (.AppImage)
- Supports `amd64` and `aarch64` (Raspberry Pi, Apple Silicon)

## ☕ Support this project

This project is developed and maintained in my free time. If it saves you time or helps you get your Kia/Hyundai connected, I'd appreciate your support:

<a href="https://buymeacoffee.com/tobiasmalct"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy me a coffee" width="217"></a>

## Quick Start

### Which installation method is right for you?

| Your setup | Recommended method |
|---|---|
| Home Assistant OS (HAOS) or Supervised | [Home Assistant Add-on](#home-assistant) |
| Home Assistant Container (Docker) | [Docker](#docker--podman) |
| NAS (Synology, QNAP, Unraid) | [Docker](#docker--podman) |
| No Docker, no Home Assistant | [Standalone App](#standalone-apps-windows-macos-linux) |

> **Note:** The Home Assistant Add-on requires **Home Assistant OS** or **Supervised** installation. If you run HA as a Docker container (e.g. on a NAS), use the Docker method instead — it works alongside your existing HA container. This is **not** a HACS integration — it's a standalone tool that generates tokens for use with the [Kia/Hyundai Connect integration](https://github.com/Hyundai-Kia-Connect/kia_uvo).

### Home Assistant

→ **[Home Assistant Setup Guide](docs/HOME_ASSISTANT.md)**

[![Add repository to Home Assistant][repo-badge]][repo-url]

[repo-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[repo-url]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FTMA84%2Fbluelink-refresh-token

### Docker / Podman

→ **[Docker Setup Guide](docs/DOCKER.md)**

Works on any system with Docker: Linux servers, Synology/QNAP NAS, Unraid, or alongside an existing HA Container installation.

```bash
docker run -d --name bluelink-token -p 9876:9876 \
  -e BRAND=eu_kia \
  -e BLUELINK_USERNAME=your@email.com \
  -e BLUELINK_PASSWORD=yourpassword \
  ghcr.io/tma84/bluelink-token:latest /run-standalone.sh
```

### Standalone Apps (Windows, macOS, Linux)

No Docker or Python needed — download from the [latest release](https://github.com/TMA84/bluelink-refresh-token/releases/latest), double-click to start, a browser window opens automatically.

| Platform | Download | Notes |
|----------|----------|-------|
| **Windows** | `BluelinkTokenGenerator.exe` | No installation needed |
| **macOS** | `BluelinkTokenGenerator-macOS.dmg` | Open DMG, drag to Applications |
| **Linux** | `BluelinkTokenGenerator-Linux.AppImage` | `chmod +x`, then double-click or run from terminal |

#### Usage

1. Download the file for your platform from the [latest release](https://github.com/TMA84/bluelink-refresh-token/releases/latest)
2. Start the app:
   - **Windows:** Double-click `BluelinkTokenGenerator.exe`
   - **macOS:** Open the `.dmg`, drag "Bluelink Token Generator" to Applications, then launch it from there
   - **Linux:** Make executable (`chmod +x BluelinkTokenGenerator-Linux.AppImage`) and double-click or run `./BluelinkTokenGenerator-Linux.AppImage`
3. A browser window opens automatically at `http://localhost:9876`
4. Select your brand (Kia or Hyundai), enter your credentials, and click "Generate Token"
5. Copy the refresh token and use it as the password in evcc or Home Assistant

> **macOS:** On first launch, macOS may block the app. Go to System Settings → Privacy & Security and click "Open Anyway".
>
> **Linux:** If double-click doesn't work, your system may need FUSE installed (`sudo apt install libfuse2` on Ubuntu/Debian). Alternatively, run with `--appimage-extract-and-run` flag.

## How it works

1. Fetches the RSA public key from Kia/Hyundai
2. Encrypts the password with RSA (same as the official app)
3. POSTs to `/auth/account/signin` with the app's `client_id`
4. Gets the authorization code directly in the 302 redirect
5. Exchanges the code for access and refresh tokens
6. Optionally transfers the token to evcc and restarts it

## Supported Brands

| Value | Brand |
|-------|-------|
| `eu_kia` | Kia (Europe) |
| `eu_hyundai` | Hyundai (Europe) |

Legacy values `kia` and `hyundai` are aliases for `eu_kia` and `eu_hyundai`.

> **Password requirements:** 8–20 characters, at least one uppercase letter, one lowercase letter, one digit, and one special character.

## API

The container exposes a REST API for programmatic token retrieval — no Web UI interaction needed.

### Authentication

Set the `API_TOKEN` environment variable to secure the API endpoints:

```bash
docker run -d --name bluelink-token -p 9876:9876 \
  -e BRAND=eu_kia \
  -e BLUELINK_USERNAME=your@email.com \
  -e BLUELINK_PASSWORD=yourpassword \
  -e API_TOKEN=my-secret-token \
  ghcr.io/tma84/bluelink-token:latest /run-standalone.sh
```

Then include the token in your requests:

```bash
curl -H "Authorization: Bearer my-secret-token" http://localhost:9876/api/tokens
```

> If `API_TOKEN` is not set, the API is accessible without authentication (suitable for local/localhost use only).

### `GET /api/tokens`

Returns the current token state for all configured vehicles.

```bash
curl http://localhost:9876/api/tokens
```

```json
{
  "vehicles": [
    {
      "brand": "eu_kia",
      "brand_name": "Kia",
      "username": "user@example.com",
      "refresh_token": "eyJ...",
      "days_remaining": 165,
      "status": "valid"
    }
  ]
}
```

Status values: `valid` (>14 days), `expiring` (≤14 days), `expired`, `unknown` (no token yet).

> **Note:** The token is only available via `GET /api/tokens` while the container is running and a token has been generated in the current session. Tokens are cleared from memory:
> - After **5 minutes** automatically (if no `API_TOKEN` is configured)
> - Immediately after a `GET /api/tokens` call (if no `API_TOKEN` is configured)
> - After **30 seconds** following an evcc transfer
> - On container restart or manual "Reset" in the Web UI
>
> If `API_TOKEN` is set, tokens remain available permanently for API access. The generated refresh token itself is valid for **180 days** at the Kia/Hyundai API.

### `POST /api/tokens`

Generate (or renew) tokens for all configured vehicles. Only renews if the token is expiring or unknown — use `"force": true` to always regenerate.

```bash
# Only renew if needed
curl -X POST http://localhost:9876/api/tokens

# Force renew all tokens
curl -X POST http://localhost:9876/api/tokens -H "Content-Type: application/json" -d '{"force": true}'
```

You can also provide credentials directly to generate a token for a single vehicle without pre-configuring it:

```bash
curl -X POST http://localhost:9876/api/tokens \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-secret-token" \
  -d '{"brand": "eu_kia", "username": "user@example.com", "password": "yourpassword"}'
```

```json
{
  "ok": true,
  "vehicles": [
    {
      "brand": "eu_kia",
      "brand_name": "Kia",
      "username": "user@example.com",
      "refresh_token": "eyJ...",
      "status": "ok",
      "message": "Token generated successfully"
    }
  ]
}
```

Vehicle status: `ok` (new token generated), `skipped` (still valid), `error` (login failed).

## Where to use the token

Use the refresh token as the **password** (not your Bluelink password) when configuring:

- [evcc](https://docs.evcc.io/en/docs/devices/vehicles#hyundai-bluelink) — Hyundai/Kia vehicle integration
- [Home Assistant Kia/Hyundai integration](https://github.com/Hyundai-Kia-Connect/kia_uvo)

## FAQ

### I can't find this in HACS

This is not a HACS integration. It's a Home Assistant **Add-on** that requires HAOS or Supervised. If you run HA as a Docker container (e.g. on a NAS), use the [Docker setup](docs/DOCKER.md) instead.

### I don't have an Add-on store in Home Assistant

Your HA installation is likely the "Container" type (common on NAS systems). The Add-on store is only available on HAOS and Supervised installations. Use the [Docker method](docs/DOCKER.md) — it runs as a separate container alongside your HA.

### Does this work on Synology / QNAP / Unraid?

Yes. Use the [Docker setup](docs/DOCKER.md) — there are NAS-specific instructions for Synology, QNAP, and Unraid.

### What's the difference between this and the old browser-based scripts?

The old scripts (e.g. from RustyDust/bluelink_refresh_token) used Selenium/Playwright to automate a real browser. They broke when Kia/Hyundai added bot detection. This tool works **headless** by reverse-engineering the official app's API calls — no browser, no CAPTCHA, no bot detection issues.

### I get "classified as an abusing request and blocked"

This error affects the old browser-based token scripts. This tool uses a different approach (direct API calls with the app's TLS fingerprint) and is not affected by this block.

## Support

Got questions or issues? [Open an issue on GitHub.](https://github.com/TMA84/bluelink-refresh-token/issues)

## Credits

Based on [bluelink_refresh_token](https://github.com/RustyDust/bluelink_refresh_token) by RustyDust.

## License

MIT

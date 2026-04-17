<p align="center">
  <img src="bluelink-token/logo.png" alt="Bluelink Token Generator" width="200">
</p>

<h1 align="center">Bluelink Token Generator</h1>

<p align="center">
  Generate Hyundai/Kia Bluelink refresh tokens for
  <a href="https://evcc.io">evcc</a> and
  <a href="https://www.home-assistant.io/">Home Assistant</a> —
  directly from a web UI, no command line needed.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/aarch64-yes-green.svg" alt="Supports aarch64">
  <img src="https://img.shields.io/badge/amd64-yes-green.svg" alt="Supports amd64">
  <img src="https://img.shields.io/github/v/release/TMA84/bluelink-refresh-token" alt="GitHub Release">
  <img src="https://img.shields.io/github/license/TMA84/bluelink-refresh-token" alt="License">
</p>

---

## About

This add-on runs a Chromium browser inside the container with the correct mobile user-agent required by the Bluelink OAuth flow. You interact with the browser through an embedded noVNC viewer to complete the login. The add-on then automatically extracts the refresh token.

### Features

- Web UI for the complete token generation flow — no terminal needed
- Supports **Hyundai** and **Kia** (selectable in UI or pre-configured)
- Auto-fill credentials if configured
- **evcc integration** — transfer the token directly to evcc and restart it automatically
- Works as a Home Assistant add-on or standalone Docker container

## Installation

1. Add this repository to your Home Assistant add-on store:

   [![Open your Home Assistant instance and show the add add-on repository dialog.][repo-badge]][repo-url]

   Or manually: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and paste:
   ```
   https://github.com/TMA84/bluelink-refresh-token
   ```

2. Find "Bluelink Token Generator" in the store and click **Install**.
3. Configure the add-on (see below).
4. Start the add-on and open the **Web UI**.

[repo-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[repo-url]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FTMA84%2Fbluelink-refresh-token

## How to use

1. Select your brand (if not pre-configured) and click **Start token generation**
2. Sign in via the embedded browser (credentials are auto-filled if configured)
3. The refresh token is extracted and displayed
4. If evcc is configured, the token is automatically sent to evcc and evcc is restarted

The generated refresh token is valid for **180 days**. After that, simply generate a new one.

## Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `brand` | `auto` (show selector), `hyundai`, or `kia` | `auto` |
| `username` | Bluelink email/username for auto-fill (optional) | |
| `password` | Bluelink password for auto-fill (optional) | |
| `evcc_url` | evcc instance URL, e.g. `http://192.168.1.100:7070` (optional) | |
| `evcc_password` | evcc admin password (optional, leave empty if not set) | |

When `brand` is set to `hyundai` or `kia`, the brand selector on the start page is skipped.

When `evcc_url` is configured, the token is automatically transferred to evcc after generation — no manual copy-paste needed. If only one Hyundai/Kia vehicle is found in evcc, the transfer and restart happen fully automatically.

## evcc Integration

The add-on can transfer the refresh token directly to an evcc instance:

1. Configure `evcc_url` (and optionally `evcc_password`) in the add-on settings
2. After token generation, the add-on connects to evcc automatically
3. If one vehicle is found → token is sent and evcc is restarted automatically
4. If multiple vehicles are found → select which ones should receive the token, evcc is restarted after transfer

This works with evcc running as a Home Assistant add-on, Docker container, or native installation.

## Where to use the token

Use the refresh token as the **password** (not your Bluelink password) when configuring:

- [evcc](https://docs.evcc.io/en/docs/devices/vehicles#hyundai-bluelink) — Hyundai/Kia vehicle integration
- [Home Assistant Kia/Hyundai integration](https://github.com/Hyundai-Kia-Connect/kia_uvo)

## Standalone with Docker

If you don't use Home Assistant, you can run the container on any system with Docker or Podman — macOS, Linux, and Windows.

### Docker Compose (recommended)

Clone the repo and edit `docker-compose.yaml` with your settings:

```bash
git clone https://github.com/TMA84/bluelink-refresh-token.git
cd bluelink-refresh-token
# edit docker-compose.yaml with your credentials
docker compose up -d
```

The `docker-compose.yaml` is pre-configured with all available options. Just fill in your values and start the container. Port `9876` is the Web UI, port `6080` is the noVNC remote browser. The `shm_size: 256m` is required for Chromium to run stable inside the container.

Then open `http://localhost:9876`.

### Docker Run

```bash
docker run -d \
  --name bluelink-token \
  -p 9876:9876 \
  -p 6080:6080 \
  --shm-size=256m \
  -e BRAND=hyundai \
  -e BLUELINK_USERNAME=your@email.com \
  -e BLUELINK_PASSWORD=yourpassword \
  -e EVCC_URL=http://192.168.1.100:7070 \
  -e EVCC_PASSWORD=adminpassword \
  ghcr.io/tma84/bluelink-token:latest \
  /run-standalone.sh
```

Then open `http://localhost:9876`.

### Podman

Replace `docker` with `podman` in the commands above. On macOS, install Podman via [podman.io](https://podman.io/).

### Environment Variables

All environment variables are optional:

| Variable | Description |
|----------|-------------|
| `BRAND` | `auto`, `hyundai`, or `kia` (default: `auto`) |
| `BLUELINK_USERNAME` | Auto-fill email/username |
| `BLUELINK_PASSWORD` | Auto-fill password |
| `EVCC_URL` | evcc URL for automatic token transfer |
| `EVCC_PASSWORD` | evcc admin password |

The image is a multi-arch manifest and works on `amd64` (Intel/AMD) and `aarch64` (Apple Silicon, Raspberry Pi).

## Support

Got questions or issues? [Open an issue on GitHub.](https://github.com/TMA84/bluelink-refresh-token/issues)

## Credits

Based on [bluelink_refresh_token](https://github.com/RustyDust/bluelink_refresh_token) by RustyDust.

## License

MIT

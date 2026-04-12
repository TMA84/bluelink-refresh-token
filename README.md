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

## Installation

1. Add this repository to your Home Assistant add-on store:

   [![Open your Home Assistant instance and show the add add-on repository dialog.][repo-badge]][repo-url]

   Or manually: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and paste:
   ```
   https://github.com/TMA84/bluelink-refresh-token
   ```

2. Find "Bluelink Token Generator" in the store and click **Install**.
3. Configure your brand and optionally your credentials (see below).
4. Start the add-on and open the **Web UI**.

[repo-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[repo-url]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FTMA84%2Fbluelink-refresh-token

## How to use

1. Select your brand (Hyundai/Kia) on the start page
2. Click **Start token generation**
3. Sign in via the embedded browser (credentials are auto-filled if configured)
4. The refresh token is extracted and displayed
5. Use the **Verify token** button to confirm it works

The generated refresh token is valid for **180 days**. After that, simply generate a new one.

## Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `brand` | Vehicle brand | `hyundai` |
| `username` | Bluelink email/username (optional, for auto-fill) | |
| `password` | Bluelink password (optional, for auto-fill) | |

## Where to use the token

Use the refresh token as the **password** (not your Bluelink password) when configuring:

- [evcc](https://docs.evcc.io/en/docs/devices/vehicles#hyundai-bluelink) — Hyundai/Kia vehicle integration
- [Home Assistant Kia/Hyundai integration](https://github.com/Hyundai-Kia-Connect/kia_uvo)

## Standalone with Docker

If you don't use Home Assistant, you can run the container directly:

```bash
docker run -d \
  --name bluelink-token \
  -p 9876:9876 \
  -p 6080:6080 \
  -e BRAND=hyundai \
  -e BLUELINK_USERNAME=your@email.com \
  -e BLUELINK_PASSWORD=yourpassword \
  ghcr.io/tma84/bluelink-token:latest
```

Then open `http://localhost:9876`. Username and password are optional — without them, the fields won't be auto-filled.

The image is a multi-arch manifest and works on both `amd64` and `aarch64` (e.g. Raspberry Pi).

## Support

Got questions or issues? [Open an issue on GitHub.](https://github.com/TMA84/bluelink-refresh-token/issues)

## Credits

Based on [bluelink_refresh_token](https://github.com/RustyDust/bluelink_refresh_token) by RustyDust.

## License

MIT

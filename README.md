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
  <a href="https://github.com/sponsors/TMA84"><img src="https://img.shields.io/badge/Sponsor_on_GitHub-♥-ea4aaa?style=for-the-badge&logo=github" alt="Sponsor on GitHub"></a>
</p>

---

## About

This add-on generates Bluelink refresh tokens for Hyundai and Kia vehicles. Since v4.1, it supports a **headless login** that works without any browser interaction — just configure your credentials and the token is generated automatically.

The headless login was developed by reverse engineering the official Kia Connect App (v2.1.27). It uses `curl_cffi` to impersonate an Android Chrome TLS fingerprint and performs the complete OAuth flow via HTTP requests.

### Features

- **Headless login** for EU Kia and EU Hyundai — no browser, no CAPTCHA, fully automatic
- **Auto-start** — token is generated on container start when credentials are configured
- **Simple Web UI** — enter credentials and click "Generate Token" (EU brands)
- **evcc integration** — transfer the token directly to evcc and restart automatically
- Browser fallback via embedded noVNC viewer for non-EU brands
- Home Assistant token expiry sensor with automation support
- Non-EU regions available via `show_all_regions` option
- Works as a Home Assistant add-on or standalone Docker/Podman container

## Installation

### Home Assistant Add-on

1. Add this repository to your Home Assistant add-on store:

   [![Open your Home Assistant instance and show the add add-on repository dialog.][repo-badge]][repo-url]

   Or manually: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and paste:
   ```
   https://github.com/TMA84/bluelink-refresh-token
   ```

2. Find "Bluelink Token Generator" in the store and click **Install**.
3. Configure username, password, and brand in the add-on settings.
4. Start the add-on — the token is generated automatically.

[repo-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[repo-url]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FTMA84%2Fbluelink-refresh-token

### Standalone with Docker Compose

```yaml
services:
  bluelink-token:
    image: ghcr.io/tma84/bluelink-token:latest
    ports:
      - "9876:9876"
      - "6080:6080"
    environment:
      - BRAND=eu_kia              # or eu_hyundai
      - BLUELINK_USERNAME=your@email.com
      - BLUELINK_PASSWORD=yourpassword
      - EVCC_URL=http://evcc:7070 # optional
      - EVCC_PASSWORD=            # optional
    shm_size: 256m
    command: ["/run-standalone.sh"]
```

Then open `http://localhost:9876`.

### Docker Run

```bash
docker run -d \
  --name bluelink-token \
  -p 9876:9876 -p 6080:6080 \
  --shm-size=256m \
  -e BRAND=eu_kia \
  -e BLUELINK_USERNAME=your@email.com \
  -e BLUELINK_PASSWORD=yourpassword \
  ghcr.io/tma84/bluelink-token:latest \
  /run-standalone.sh
```

Replace `docker` with `podman` if using Podman.

## How it works

### Headless Login (EU Kia / EU Hyundai)

When credentials are configured, the add-on performs a fully automatic login on startup:

1. Fetches the RSA public key from `/auth/api/v1/accounts/certs`
2. Encrypts the password with RSA (same as the official app)
3. POSTs to `/auth/account/signin` with the app's `client_id` and encrypted password
4. Gets the authorization code directly in the 302 redirect
5. Exchanges the code for access and refresh tokens

No browser, no CAPTCHA, no manual interaction needed.

### Browser Fallback (all regions)

For non-EU brands or if the headless login fails, the add-on falls back to a browser-based flow:

1. Opens a Chromium browser with the correct mobile user-agent
2. Auto-fills credentials if configured
3. You complete the login via the embedded noVNC viewer
4. The token is extracted automatically

### evcc Integration

If `EVCC_URL` is configured, the token is automatically transferred to evcc after generation. If only one Hyundai/Kia vehicle is found, the transfer and evcc restart happen fully automatically.

## Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `brand` | Region and brand (see table below) | `auto` |
| `country` | Country code for EU Hyundai (e.g. `DE`, `FR`, `PL`) | `DE` |
| `username` | Bluelink email/username | |
| `password` | Bluelink password | |
| `evcc_url` | evcc instance URL (optional) | |
| `evcc_password` | evcc admin password (optional) | |
| `show_all_regions` | Show non-EU regions in brand selector | `false` |

### Supported Regions and Brands

| Value | Region | Brand | Headless Login |
|-------|--------|-------|:--------------:|
| `eu_kia` | Europe | Kia | ✅ |
| `eu_hyundai` | Europe | Hyundai | ✅ |
| `cn_kia` | China | Kia | Browser |
| `cn_hyundai` | China | Hyundai | Browser |
| `au_kia` | Australia | Kia | Browser |
| `au_hyundai` | Australia | Hyundai | Browser |
| `nz_kia` | New Zealand | Kia | Browser |
| `in_kia` | India | Kia | Browser |
| `in_hyundai` | India | Hyundai | Browser |
| `br_hyundai` | Brazil | Hyundai | Browser |

Legacy values `kia` and `hyundai` are aliases for `eu_kia` and `eu_hyundai`.

Non-EU regions are hidden by default. Enable them with `show_all_regions: true` in the add-on config or `SHOW_ALL_REGIONS=true` as environment variable.

### Environment Variables (Docker/Podman)

| Variable | Description |
|----------|-------------|
| `BRAND` | `auto`, `eu_kia`, `eu_hyundai`, etc. (default: `auto`) |
| `BLUELINK_USERNAME` | Bluelink email/username |
| `BLUELINK_PASSWORD` | Bluelink password |
| `EVCC_URL` | evcc URL for automatic token transfer |
| `EVCC_PASSWORD` | evcc admin password |
| `COUNTRY` | Country code for EU Hyundai (default: `DE`) |
| `SHOW_ALL_REGIONS` | `true` to show non-EU regions in UI |

## Token Expiry

The refresh token is valid for **180 days**. After that, simply restart the add-on to generate a new one.

When running as a Home Assistant add-on, a sensor `sensor.bluelink_token_expiry` is automatically created. Use it to set up an expiry reminder:

```yaml
automation:
  - alias: "Bluelink Token Expiry Reminder"
    trigger:
      - platform: template
        value_template: >
          {{ (as_timestamp(states('sensor.bluelink_token_expiry')) - as_timestamp(now()))
             / 86400 < 14 }}
    action:
      - service: notify.notify
        data:
          title: "Bluelink Token expires soon"
          message: >
            Your Bluelink token expires in
            {{ ((as_timestamp(states('sensor.bluelink_token_expiry')) - as_timestamp(now())) / 86400) | round(0) }}
            days. Please regenerate it.
```

## Where to use the token

Use the refresh token as the **password** (not your Bluelink password) when configuring:

- [evcc](https://docs.evcc.io/en/docs/devices/vehicles#hyundai-bluelink) — Hyundai/Kia vehicle integration
- [Home Assistant Kia/Hyundai integration](https://github.com/Hyundai-Kia-Connect/kia_uvo)

## Support

Got questions or issues? [Open an issue on GitHub.](https://github.com/TMA84/bluelink-refresh-token/issues)

### ☕ Sponsor this project

This project is developed and maintained in my free time. If it saves you time or helps you get your Kia/Hyundai connected, I'd appreciate your support:

<a href="https://github.com/sponsors/TMA84"><img src="https://img.shields.io/badge/Sponsor_on_GitHub-♥-ea4aaa?style=for-the-badge&logo=github" alt="Sponsor on GitHub"></a>

## Credits

Based on [bluelink_refresh_token](https://github.com/RustyDust/bluelink_refresh_token) by RustyDust.

## License

MIT

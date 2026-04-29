# Home Assistant Setup

## Installation

1. Add this repository to your Home Assistant app store:

   [![Open your Home Assistant instance and show the add app repository dialog.][repo-badge]][repo-url]

   Or manually: **Settings → Add-ons → Add-ons store (bottom right) → ⋮ → Repositories** and paste:
   ```
   https://github.com/TMA84/bluelink-refresh-token
   ```

2. Find "Bluelink Token Generator" in the store and click **Install**.
3. Configure the app (see below).
4. Start the app — tokens are generated automatically.

[repo-badge]: https://my.home-assistant.io/badges/supervisor_add_app_repository.svg
[repo-url]: https://my.home-assistant.io/redirect/supervisor_add_app_repository/?repository_url=https%3A%2F%2Fgithub.com%2FTMA84%2Fbluelink-refresh-token

## Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `vehicles` | List of vehicles with brand/username/password | `[]` |
| `country` | Country code for EU Hyundai (e.g. `DE`, `FR`, `PL`) | `DE` |
| `evcc_url` | evcc instance URL (optional) | |
| `evcc_password` | evcc admin password (optional) | |

### Vehicle Configuration

Each vehicle entry:

| Field | Description |
|-------|-------------|
| `brand` | `eu_kia` or `eu_hyundai` |
| `username` | Bluelink email/username |
| `password` | Bluelink password (8-20 characters) |

Example:
```yaml
vehicles:
  - brand: eu_kia
    username: kia@email.com
    password: kiapassword
  - brand: eu_hyundai
    username: hyundai@email.com
    password: hyundaipassword
country: DE
evcc_url: http://192.168.1.100:7070
evcc_password: adminpass
```

> **Password requirements:** 8–20 characters, at least one uppercase letter, one lowercase letter, one digit, and one special character.

## Token Expiry Sensors

A sensor is created per vehicle after token generation:

- `sensor.bluelink_token_expiry_eu_kia_<hash>` — for Kia vehicles
- `sensor.bluelink_token_expiry_eu_hyundai_<hash>` — for Hyundai vehicles

The `<hash>` is derived from the username to support multiple accounts per brand.

| Attribute | Description |
|-----------|-------------|
| `state` | Expiry date (e.g. `2026-10-14`) |
| `generated` | Date and time the token was generated |
| `expires` | Date and time the token expires |
| `days_remaining` | Days until expiry (180 at generation) |
| `brand` | `eu_kia` or `eu_hyundai` |
| `username` | Account email |

On each app restart, each vehicle's sensor is checked individually:
- Token still valid (>14 days) → skipped
- Token expiring soon (<14 days) → automatic renewal

## Automatic Token Renewal

### Via Automation (recommended)

Create an automation that restarts the app when any token is about to expire. Use the sensor name from the app log.

**Settings → Automations → New Automation → ⋮ → Edit as YAML:**

```yaml
alias: Bluelink Token Auto-Renew
description: Renews Bluelink tokens automatically 14 days before expiry
triggers:
  - trigger: template
    value_template: >-
      {% set sensors = states.sensor
        | selectattr('entity_id', 'match', 'sensor.bluelink_token_expiry_')
        | list %}
      {% for s in sensors %}
        {% if (as_timestamp(s.state) - as_timestamp(now())) / 86400 < 14 %}
          true
        {% endif %}
      {% endfor %}
actions:
  - action: hassio.addon_restart
    data:
      addon: local_bluelink_token
mode: single
```

> **Note:** The addon identifier is `local_bluelink_token`. You can verify this in **Settings → Apps → Bluelink Token Generator** — the slug is shown in the URL.

### Via Start on Boot

Enable **Start on boot** in the app settings. The app checks each vehicle's token expiry on every HA restart and only renews those that need it.

## Expiry Reminder Notification

```yaml
alias: Bluelink Token Expiry Reminder
description: Notification when any Bluelink token is about to expire
triggers:
  - trigger: template
    value_template: >-
      {% set sensors = states.sensor
        | selectattr('entity_id', 'match', 'sensor.bluelink_token_expiry_')
        | list %}
      {% for s in sensors %}
        {% if (as_timestamp(s.state) - as_timestamp(now())) / 86400 < 14 %}
          true
        {% endif %}
      {% endfor %}
actions:
  - action: notify.notify
    data:
      title: Bluelink Token expires soon
      message: >-
        One or more Bluelink tokens expire within 14 days. Please restart
        the Bluelink Token Generator app to renew them.
mode: single
```

## evcc Integration

If `evcc_url` is configured, tokens are automatically transferred to evcc after generation:

1. Connects to evcc and logs in (if password is set)
2. Finds all Hyundai/Kia vehicles
3. Matches the correct token to each vehicle by brand (Kia token → Kia vehicle, Hyundai token → Hyundai vehicle)
4. Restarts evcc

This works with evcc running as a HA app, Docker container, or native installation.

## Where to use the token

Use the refresh token as the **password** (not your Bluelink password) when configuring:

- [evcc](https://docs.evcc.io/en/docs/devices/vehicles#hyundai-bluelink) — Hyundai/Kia vehicle integration
- [Home Assistant Kia/Hyundai integration](https://github.com/Hyundai-Kia-Connect/kia_uvo)

## For EU, homeassistant Kia/Hyundai Uvo:
follow readme of repo below, with below specified values:
[Home Assistant Kia/Hyundai integration](https://github.com/Hyundai-Kia-Connect/kia_uvo)
- Use your kia/Hyundai account email for 'username'
- Use above generated token for 'token'
- leave 'pin' empty


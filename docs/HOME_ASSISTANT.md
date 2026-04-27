# Home Assistant Setup

## Installation

1. Add this repository to your Home Assistant add-on store:

   [![Open your Home Assistant instance and show the add add-on repository dialog.][repo-badge]][repo-url]

   Or manually: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and paste:
   ```
   https://github.com/TMA84/bluelink-refresh-token
   ```

2. Find "Bluelink Token Generator" in the store and click **Install**.
3. Configure the add-on (see below).
4. Start the add-on — the token is generated automatically.

[repo-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[repo-url]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FTMA84%2Fbluelink-refresh-token

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

## Token Expiry Sensor

After each token generation, a sensor `sensor.bluelink_token_expiry` is created automatically.

| Attribute | Description |
|-----------|-------------|
| `state` | Expiry date (e.g. `2026-10-14`) |
| `generated` | Date and time the token was generated |
| `expires` | Date and time the token expires |
| `days_remaining` | Days until expiry (180 at generation) |
| `brand` | `eu_kia` or `eu_hyundai` |

On each addon restart, the sensor is checked:
- Token still valid (>14 days) → no action
- Token expiring soon (<14 days) → automatic renewal

## Automatic Token Renewal

### Via Automation (recommended)

Create an automation that restarts the addon when the token is about to expire.

**Settings → Automations → New Automation → ⋮ → Edit as YAML:**

```yaml
alias: Bluelink Token Auto-Renew
description: Renews the Bluelink token automatically 14 days before expiry
triggers:
  - trigger: template
    value_template: >-
      {{ (as_timestamp(states('sensor.bluelink_token_expiry')) -
      as_timestamp(now())) / 86400 < 14 }}
actions:
  - action: hassio.addon_restart
    data:
      addon: local_bluelink_token
mode: single
```

> **Note:** The addon identifier is `local_bluelink_token`. You can verify this in **Settings → Add-ons → Bluelink Token Generator** — the slug is shown in the URL.

### Via Start on Boot

Enable **Start on boot** in the addon settings. The addon checks the token expiry on each HA restart and only renews if needed.

## Expiry Reminder Notification

Get a notification when the token is about to expire:

```yaml
alias: Bluelink Token Expiry Reminder
description: Sends a notification 14 days before the token expires
triggers:
  - trigger: template
    value_template: >-
      {{ (as_timestamp(states('sensor.bluelink_token_expiry')) -
      as_timestamp(now())) / 86400 < 14 }}
actions:
  - action: notify.notify
    data:
      title: Bluelink Token expires soon
      message: >-
        Your Bluelink token expires in
        {{ ((as_timestamp(states('sensor.bluelink_token_expiry')) -
        as_timestamp(now())) / 86400) | round(0) }} days. Please regenerate it.
mode: single
```

## evcc Integration

If `evcc_url` is configured, the token is automatically transferred to evcc after generation:

1. Connects to evcc and logs in (if password is set)
2. Finds all Hyundai/Kia vehicles
3. Updates the refresh token on each vehicle
4. Restarts evcc

This works with evcc running as a HA add-on, Docker container, or native installation.

## Where to use the token

Use the refresh token as the **password** (not your Bluelink password) when configuring:

- [evcc](https://docs.evcc.io/en/docs/devices/vehicles#hyundai-bluelink) — Hyundai/Kia vehicle integration
- [Home Assistant Kia/Hyundai integration](https://github.com/Hyundai-Kia-Connect/kia_uvo)

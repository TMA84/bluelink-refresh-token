# Home Assistant Setup

## Requirements

This add-on requires **Home Assistant OS (HAOS)** or a **Supervised** installation. These are the only installation types that support the Add-on store.

| HA Installation Type | Add-on supported? | Alternative |
|---|---|---|
| Home Assistant OS (HAOS) | ✅ Yes | — |
| Supervised | ✅ Yes | — |
| Container (Docker) | ❌ No | Use [Docker setup](DOCKER.md) alongside your HA container |
| Core (venv) | ❌ No | Use [Docker setup](DOCKER.md) or [Standalone app](../README.md#standalone-apps-windows-macos-linux) |

> **Not a HACS integration:** This is a Home Assistant **Add-on** (installed via the Add-on store), not a HACS custom component. You will not find it in HACS. The generated token is used with the separate [Kia/Hyundai Connect integration](https://github.com/Hyundai-Kia-Connect/kia_uvo).

## Installation

1. Add this repository to your Home Assistant app store:

   [![Open your Home Assistant instance and show the add app repository dialog.][repo-badge]][repo-url]

   Or manually:
   - **English:** Settings → Add-ons → Add-on store (bottom right) → ⋮ → Repositories
   - **Deutsch:** Einstellungen → Apps → Apps installieren → ⋮ → Repositories

   Paste:
   ```
   https://github.com/TMA84/bluelink-refresh-token
   ```

2. Find "Bluelink Token Generator" in the store and click **Install**.
3. Configure the app (see below).
4. Start the app — tokens are generated automatically.

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

The add-on has **built-in auto-renewal**: it checks token expiry every 24 hours and automatically renews tokens that are about to expire (<14 days remaining). A persistent notification is created in HA when a token is renewed or if renewal fails.

**No automation or cron job needed** — just enable "Start on boot" and leave the add-on running.

### Recommended Setup

1. Enable **Start on boot** in the add-on settings
2. That's it — the add-on handles everything automatically

### Optional: Custom Automation (legacy)

If you prefer explicit control or want to trigger renewal at a specific time, you can still create an automation. This is **not required** — the add-on already does this internally.

<details>
<summary>Show legacy automation YAML</summary>

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

</details>

## Expiry Reminder Notification

The add-on creates a persistent notification automatically when a token is renewed or fails. If you additionally want a mobile notification, you can use this automation:

```yaml
alias: Bluelink Token Expiry Reminder
description: Mobile notification when any Bluelink token is about to expire
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

→ **[Full evcc Integration Guide](EVCC.md)**

If `evcc_url` is configured, tokens are automatically transferred to evcc after generation. This works with evcc running as a HA add-on, Docker container, or native installation.

## kia_uvo Integration

→ **[Full kia_uvo Integration Guide](KIA_UVO.md)**

The add-on can automatically transfer the generated refresh token to the [Kia/Hyundai Connect integration](https://github.com/Hyundai-Kia-Connect/kia_uvo) (kia_uvo) in Home Assistant — fully automatic, no manual token copying needed.

## Where to use the token

Use the refresh token as the **password** (not your Bluelink password) when configuring:

- [evcc](https://docs.evcc.io/en/docs/devices/vehicles#hyundai-bluelink) — Hyundai/Kia vehicle integration
- [Home Assistant Kia/Hyundai integration](https://github.com/Hyundai-Kia-Connect/kia_uvo)

## Using the token with Kia/Hyundai Connect integration

When configuring the [Home Assistant Kia/Hyundai integration](https://github.com/Hyundai-Kia-Connect/kia_uvo):

- **Username:** Your Kia/Hyundai account email
- **Token:** The generated refresh token (not your Bluelink password)
- **PIN:** Leave empty


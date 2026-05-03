# kia_uvo Integration

Transfer generated refresh tokens directly to the [Kia/Hyundai Connect integration](https://github.com/Hyundai-Kia-Connect/kia_uvo) (kia_uvo) in Home Assistant — fully automatic, no manual token copying needed.

This works both as a **Home Assistant Add-on** and as a **standalone Docker container** (with additional configuration).

> **See also:** [Home Assistant Setup](HOME_ASSISTANT.md) | [Docker Setup](DOCKER.md) | [evcc Integration](EVCC.md)

## How it works

After generating a token, the add-on:

1. Detects if kia_uvo is installed in Home Assistant
2. If a config entry exists → runs the reconfigure flow to update the token
3. If no config entry exists → runs the initial setup flow to configure the integration

This happens **fully automatically** — no manual token copying needed.

## Requirements

- The [kia_uvo integration](https://github.com/Hyundai-Kia-Connect/kia_uvo) must be installed via HACS
- The add-on uses the Supervisor API automatically (no additional configuration needed)

## Configuration (Addon)

No configuration needed — the add-on detects kia_uvo automatically and uses the Supervisor token for authentication.

Optional settings (only needed for Docker/standalone):

| Option | Description | Default |
|--------|-------------|---------|
| `ha_kia_uvo_transfer` | Enable/disable transfer (`auto`, `true`, `false`) | `auto` |
| `ha_kia_uvo_pin` | Vehicle PIN for kia_uvo | |
| `ha_url` | HA URL (only for Docker/standalone) | |
| `ha_token` | HA Long-Lived Access Token (only for Docker/standalone) | |

## Web UI

The "Send to kia_uvo" card in the Web UI shows:
- Transfer status (success/failure)
- "Re-send to kia_uvo" button for manual trigger

## First-time setup

If kia_uvo is installed but not yet configured, the add-on will automatically create the config entry on the first token generation. No manual configuration in HA needed.

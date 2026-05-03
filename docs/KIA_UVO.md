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

## Configuration

### `ha_kia_uvo_transfer` setting

| Value | Behavior |
|-------|----------|
| `auto` (default) | Automatically detects if kia_uvo is installed and transfers the token. In the HA Add-on, this means the transfer is attempted on every token generation if kia_uvo is present. |
| `true` | Always transfer — skips detection and assumes kia_uvo is installed. |
| `false` | Disabled — no transfer, no detection, kia_uvo card hidden in Web UI. |

### Home Assistant Add-on

In the add-on, `auto` mode works without any additional configuration — the Supervisor API handles authentication automatically. Set to `false` if you don't use the kia_uvo integration and want to disable the feature entirely.

| Option | Description | Default |
|--------|-------------|---------|
| `ha_kia_uvo_transfer` | Enable/disable transfer | `auto` |
| `ha_kia_uvo_pin` | Vehicle PIN for kia_uvo | |

### Docker / Standalone

For Docker or standalone setups, you need to provide the HA connection details manually:

| Variable | Description | Required |
|----------|-------------|----------|
| `HA_URL` | Home Assistant URL (e.g. `http://192.168.1.100:8123`) | Yes |
| `HA_TOKEN` | Long-Lived Access Token | Yes |
| `HA_KIA_UVO_TRANSFER` | `auto`, `true`, or `false` | No (default: `auto`) |
| `HA_KIA_UVO_PIN` | Vehicle PIN | No |

## Web UI

The "Send to kia_uvo" card in the Web UI shows:
- Transfer status (success/failure)
- "Re-send to kia_uvo" button for manual trigger

## First-time setup

If kia_uvo is installed but not yet configured, the add-on will automatically create the config entry on the first token generation. No manual configuration in HA needed.

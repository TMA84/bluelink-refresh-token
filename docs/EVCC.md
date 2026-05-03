# evcc Integration

Automatically transfer generated Bluelink refresh tokens to [evcc](https://evcc.io) after generation — no manual token copying needed.

This works with evcc running as a Home Assistant add-on, Docker container, or native installation.

> **See also:** [Home Assistant Setup](HOME_ASSISTANT.md) | [Docker Setup](DOCKER.md) | [kia_uvo Integration](KIA_UVO.md)

## How it works

If `evcc_url` is configured, tokens are automatically transferred to evcc after generation:

1. Connects to evcc and logs in (if password is set)
2. Finds all Hyundai/Kia vehicles
3. Matches the correct token to each vehicle by brand (Kia token → Kia vehicle, Hyundai token → Hyundai vehicle)
4. Restarts evcc

## Configuration

### Home Assistant Add-on

| Option | Description | Default |
|--------|-------------|---------|
| `evcc_url` | evcc instance URL (e.g. `http://192.168.1.100:7070`) | |
| `evcc_password` | evcc admin password (optional) | |

### Docker / Standalone

Set via environment variables:

| Variable | Description |
|----------|-------------|
| `EVCC_URL` | evcc URL for automatic token transfer |
| `EVCC_PASSWORD` | evcc admin password |

Example:

```bash
docker run -d --name bluelink-token -p 9876:9876 \
  -e BRAND=eu_kia \
  -e BLUELINK_USERNAME=your@email.com \
  -e BLUELINK_PASSWORD=yourpassword \
  -e EVCC_URL=http://evcc:7070 \
  -e EVCC_PASSWORD=adminpass \
  ghcr.io/tma84/bluelink-token:latest /run-standalone.sh
```

## evcc vehicle configuration

In your evcc configuration, set up the vehicle with a placeholder token. The Bluelink Token Generator will update it automatically:

```yaml
vehicles:
  - name: kia
    type: template
    template: kia
    title: Kia
    user: your@email.com
    password: placeholder  # will be replaced by the generated refresh token
    vin: WXXXXXXXXXXXXXXXXX
    capacity: 77.4
```

See the [evcc documentation](https://docs.evcc.io/en/docs/devices/vehicles#hyundai-bluelink) for full vehicle configuration details.

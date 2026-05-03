# API Documentation

The container exposes a REST API for programmatic token retrieval — no Web UI interaction needed.

> **See also:** [Docker Setup](DOCKER.md) | [Home Assistant Setup](HOME_ASSISTANT.md) | [README](../README.md)

## Authentication

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

## `GET /api/tokens`

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

## `POST /api/tokens`

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

# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 6.x.x  | ✅ Yes    |
| < 6.0   | ❌ No    |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Use [GitHub Security Advisories](https://github.com/TMA84/bluelink-refresh-token/security/advisories/new) to report privately

I'll work with you to understand the issue and coordinate a fix before any public disclosure.

## Scope

This project handles sensitive data including:

- Kia/Hyundai account credentials (username, password)
- OAuth refresh tokens
- Home Assistant Long-Lived Access Tokens
- Vehicle PINs

Security issues in any of these areas are taken seriously.

## Security Measures

- Credentials are never logged in plain text
- Tokens are cleared from memory after use (configurable via `API_TOKEN`)
- HTTPS supported for all external API communication
- Secret scanning and push protection enabled on this repository
- Dependencies monitored via Dependabot
- Static analysis via CodeQL

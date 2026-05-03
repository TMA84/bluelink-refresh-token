#!/usr/bin/env python3
"""Bluelink Token Generator - Headless Web Application"""

import os, re, time, threading, json, base64
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
import requests as req_lib
from flask import Flask, request, jsonify, redirect as flask_redirect
import html as html_lib

from curl_cffi import requests as curl_requests
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

from kia_uvo import _auto_kia_uvo_transfer, _kia_uvo_config
from evcc import (
    _auto_evcc_transfer as _auto_evcc_transfer_impl,
    evcc_get_vehicles,
    evcc_update_vehicle,
    evcc_restart as evcc_restart_impl,
)

app = Flask(__name__)

VERSION = "dev"
try:
    for _path in ["/app/config.yaml", "/config.yaml", "config.yaml", "../config.yaml"]:
        try:
            with open(_path) as _f:
                for _line in _f:
                    _m = re.match(r'^version:\s*"(.+)"', _line)
                    if _m:
                        VERSION = _m.group(1)
                        break
            if VERSION != "dev":
                break
        except FileNotFoundError:
            continue
except Exception:
    pass

state = {
    "status": "idle",  # idle, processing, success, error
    "vehicles": [],    # list of {brand, username, refresh_token, access_token, status, error}
    "error": None,
    "log": [],
    "brand_override": None,
    # Legacy single-vehicle compat
    "refresh_token": None, "access_token": None, "test_result": "",
}

_MOBILE_UA = "Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus Build/JRO03C) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19_CCS_APP_AOS"


def _get_vehicles_config():
    """Get vehicles from VEHICLES_JSON env var, or fall back to single BRAND/USERNAME/PASSWORD."""
    vehicles = []
    # Try VEHICLES_JSON first (HA addon config)
    vj = os.environ.get("VEHICLES_JSON", "").strip()
    if vj and vj != "[]":
        try:
            parsed = json.loads(vj)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        vehicles.append(item)
                    elif isinstance(item, str):
                        try:
                            obj = json.loads(item)
                            if isinstance(obj, dict):
                                vehicles.append(obj)
                        except Exception:
                            pass
            elif isinstance(parsed, dict):
                vehicles.append(parsed)
        except json.JSONDecodeError:
            # bashio may output concatenated JSON objects: {...}{...}
            # Try to split and parse individually
            try:
                import re as _re
                for m in _re.finditer(r'\{[^{}]*\}', vj):
                    try:
                        obj = json.loads(m.group())
                        if isinstance(obj, dict) and "brand" in obj:
                            vehicles.append(obj)
                    except Exception:
                        pass
            except Exception:
                pass
            if not vehicles:
                print(f"[WARN] Could not parse VEHICLES_JSON: {vj[:200]}", flush=True)
        except Exception as e:
            print(f"[WARN] Could not parse VEHICLES_JSON: {e} — raw: {vj[:200]}", flush=True)
    # Fallback: single vehicle from env vars (Docker standalone)
    if not vehicles:
        brand = os.environ.get("BRAND", "auto").lower()
        username = os.environ.get("BLUELINK_USERNAME", "")
        password = os.environ.get("BLUELINK_PASSWORD", "")
        if username and password:
            brand = BRAND_ALIASES.get(brand, brand)
            if brand == "auto":
                brand = "eu_kia"
            vehicles = [{"brand": brand, "username": username, "password": password}]
    return vehicles

BRAND_CONFIG = {
    # ── Europe ──────────────────────────────────────────────
    "eu_kia": {
        "client_id": "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a",
        "client_secret": "secret",
        "login_url": "https://idpconnect-eu.kia.com/auth/api/v2/user/oauth2/authorize?ui_locales=en&scope=openid%20profile%20email%20phone&response_type=code&client_id=peukiaidm-online-sales&redirect_uri=https://www.kia.com/api/bin/oneid/login&state=aHR0cHM6Ly93d3cua2lhLmNvbTo0NDMvZGUvP21zb2NraWQ9MjM1NDU0ODBmNmUyNjg5NDIwMmU0MDBjZjc2OTY5NWQmX3RtPTE3NTYzMTg3MjY1OTImX3RtPTE3NTYzMjQyMTcxMjY=_default",
        "token_url": "https://idpconnect-eu.kia.com/auth/api/v2/user/oauth2/token",
        "redirect_url_final": "https://prd.eu-ccapi.kia.com:8080/api/v1/user/oauth2/redirect",
        "redirect_url": "https://idpconnect-eu.kia.com/auth/api/v2/user/oauth2/authorize?response_type=code&client_id=fdc85c00-0a2f-4c64-bcb4-2cfb1500730a&redirect_uri=https://prd.eu-ccapi.kia.com:8080/api/v1/user/oauth2/redirect&lang=en&state=ccsp",
        "success_selector": "a[class='logout user']",
        "user_agent": _MOBILE_UA,
        "region_name": "Europe",
        "brand_name": "Kia",
    },
    "eu_hyundai": {
        "client_id": "6d477c38-3ca4-4cf3-9557-2a1929a94654",
        "client_secret": "KUy49XxPzLpLuoK0xhBC77W6VXhmtQR9iQhmIFjjoY4IpxsV",
        "login_url_template": "https://idpconnect-eu.hyundai.com/auth/api/v2/user/oauth2/authorize?client_id=peuhyundaiidm-ctb&redirect_uri=https%3A%2F%2Fctbapi.hyundai-europe.com%2Fapi%2Fauth&nonce=&state={country}_&scope=openid+profile+email+phone&response_type=code&connector_client_id=peuhyundaiidm-ctb&connector_scope=&connector_session_key=&country=&captcha=1&ui_locales=en-US",
        "token_url": "https://idpconnect-eu.hyundai.com/auth/api/v2/user/oauth2/token",
        "redirect_url_final": "https://prd.eu-ccapi.hyundai.com:8080/api/v1/user/oauth2/token",
        "redirect_url": "https://idpconnect-eu.hyundai.com/auth/api/v2/user/oauth2/authorize?response_type=code&client_id=6d477c38-3ca4-4cf3-9557-2a1929a94654&redirect_uri=https://prd.eu-ccapi.hyundai.com:8080/api/v1/user/oauth2/token&lang=en&state=ccsp",
        "success_selector": "button.mail_check",
        "user_agent": _MOBILE_UA,
        "region_name": "Europe",
        "brand_name": "Hyundai",
    },
}

# Legacy aliases
BRAND_ALIASES = {
    "kia": "eu_kia",
    "hyundai": "eu_hyundai",
}

STYLE = """
:root {
  --evcc-green: #0fde41; --evcc-darker-green: #0ba631; --evcc-darkest-green: #076f20;
  --evcc-yellow: #faf000; --evcc-dark-yellow: #f6bb0f;
  --evcc-orange: #ff9000; --evcc-red: #fc440f;
  --bg: #f3f3f7; --surface: #ffffff; --surface-border: #f9f9fb;
  --text: #28293e; --text-secondary: #93949e;
  --border: #e2e8f0;
  --primary: #0ba631; --primary-hover: #076f20; --primary-light: #e6f9ec;
  --success: #0ba631; --success-bg: #e6f9ec;
  --error: #fc440f; --error-bg: #fff0ec;
  --warning: #ff9000; --warning-bg: #fff5e6;
  --info: #0ba631; --info-bg: #e6f9ec;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Montserrat', system-ui, -apple-system, 'Segoe UI', sans-serif;
       background: var(--bg); color: var(--text); min-height: 100vh; font-size: 14px; }
.header { background: var(--text); padding: 20px 24px; margin-bottom: 24px; }
.header-inner { max-width: 800px; margin: 0 auto; display: flex; align-items: center; gap: 14px; }
.header h1 { font-size: 18px; font-weight: bold; color: white; text-transform: uppercase; }
.header .brand { font-size: 11px; font-weight: bold; color: var(--evcc-green);
                 background: rgba(15,222,65,0.15); padding: 3px 12px; border-radius: 20px;
                 text-transform: uppercase; letter-spacing: 0.8px; margin-right: auto; }
.container { max-width: 800px; margin: 0 auto; padding: 0 16px 40px; }
.card { background: var(--surface); border-radius: 1rem; padding: 1.25rem;
        margin-bottom: 16px; }
.card-title { font-size: 1.25rem; font-weight: bold; margin-bottom: 16px; text-transform: uppercase; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 10px 24px;
       border-radius: 8px; border: 2px solid transparent; font-size: 14px; font-weight: bold;
       cursor: pointer; text-decoration: none; transition: all 0.25s; font-family: inherit; }
.btn-primary { background: var(--primary); color: var(--bg); border-color: var(--primary); }
.btn-primary:hover { background: var(--primary-hover); border-color: var(--primary-hover); }
.btn-secondary { background: transparent; color: var(--primary); border-color: var(--primary); }
.btn-secondary:hover { color: var(--primary-hover); border-color: var(--primary-hover); }
.btn-danger { background: transparent; color: var(--error); border-color: var(--error); }
.btn-danger:hover { background: var(--error-bg); }
.token-label { font-size: 11px; font-weight: bold; color: var(--primary);
               text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.token-box { background: var(--bg); border: 1px solid var(--border); padding: 16px 18px;
             border-radius: 10px; word-break: break-all;
             font-family: 'JetBrains Mono', 'Roboto Mono', monospace;
             font-size: 13px; line-height: 1.7; border-left: 3px solid var(--primary); }
.copy-link { color: var(--primary); cursor: pointer; font-size: 13px; border: none;
             background: none; font-family: inherit; margin-top: 8px; display: inline-block; font-weight: bold; }
.copy-link:hover { color: var(--primary-hover); }
.notice { padding: 14px 18px; border-radius: 10px; margin-bottom: 16px;
          font-size: 14px; line-height: 1.5; }
.notice-success { background: var(--success-bg); color: var(--success); }
.notice-error { background: var(--error-bg); color: var(--error); }
.notice-warning { background: var(--warning-bg); color: var(--warning); }
.notice-info { background: var(--info-bg); color: var(--info); }
.divider { border: none; border-top: 1px solid var(--border); margin: 20px 0; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
.log { background: var(--text); color: var(--text-secondary); padding: 16px 18px; border-radius: 10px;
       font-family: 'JetBrains Mono', 'Roboto Mono', monospace; font-size: 12px;
       max-height: 200px; overflow-y: auto; margin: 12px 0; line-height: 1.8; }
.log .ok { color: var(--evcc-green); } .log .warn { color: var(--evcc-dark-yellow); } .log .err { color: var(--evcc-red); }
.paste-row { display: flex; gap: 8px; margin-bottom: 4px; }
.paste-row input { flex: 1; padding: 10px 14px; border: 1px solid var(--border);
                   border-radius: 10px; font-size: 14px; font-family: inherit;
                   background: var(--surface); color: var(--text);
                   -webkit-text-security: disc; transition: border-color 0.25s; }
.paste-row input:focus { outline: none; border-color: var(--primary); }
.paste-row button { white-space: nowrap; }
.hint { font-size: 12px; color: var(--text-secondary); margin-top: 6px; line-height: 1.5; }
.section-label { font-size: 13px; font-weight: bold; color: var(--text-secondary);
                 margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
p { line-height: 1.6; }
details summary { cursor: pointer; font-size: 13px; color: var(--text-secondary); font-weight: bold; }
details summary:hover { color: var(--primary); }
select, input[type="text"], input[type="password"] {
  background: var(--surface); color: var(--text); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px 14px; font-size: 14px; font-family: inherit;
  transition: border-color 0.25s; }
select:focus, input[type="text"]:focus, input[type="password"]:focus {
  outline: none; border-color: var(--primary); }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #1a1a2e; --surface: #16213e; --surface-border: #1a1a2e;
    --text: #e8e8e8; --text-secondary: #a0a0b0;
    --border: #2a2a4a;
    --primary: #0fde41; --primary-hover: #0ba631; --primary-light: #0a2e14;
    --success: #0fde41; --success-bg: #0a2e14;
    --error: #fc440f; --error-bg: #2e1008;
    --warning: #ff9000; --warning-bg: #2e1e08;
    --info: #0fde41; --info-bg: #0a2e14;
  }
  :root:not([data-theme="light"]) .header { background: #0f0f1a; }
  :root:not([data-theme="light"]) .log { background: #0f0f1a; }
  :root:not([data-theme="light"]) .token-box { background: #0f0f1a; border-color: #2a2a4a; }
}
:root[data-theme="dark"] {
  --bg: #1a1a2e; --surface: #16213e; --surface-border: #1a1a2e;
  --text: #e8e8e8; --text-secondary: #a0a0b0;
  --border: #2a2a4a;
  --primary: #0fde41; --primary-hover: #0ba631; --primary-light: #0a2e14;
  --success: #0fde41; --success-bg: #0a2e14;
  --error: #fc440f; --error-bg: #2e1008;
  --warning: #ff9000; --warning-bg: #2e1e08;
  --info: #0fde41; --info-bg: #0a2e14;
}
:root[data-theme="dark"] .header { background: #0f0f1a; }
:root[data-theme="dark"] .log { background: #0f0f1a; }
:root[data-theme="dark"] .token-box { background: #0f0f1a; border-color: #2a2a4a; }
.theme-toggle { background: none; border: none; cursor: pointer; font-size: 18px;
  padding: 4px 8px; border-radius: 6px; color: white; opacity: 0.7; transition: opacity 0.2s; }
.theme-toggle:hover { opacity: 1; }
"""

SCRIPT = """
function bp(path) { return (window.BASE_PATH || '') + path; }
function copyToken(id) {
    var text = document.getElementById(id).innerText;
    navigator.clipboard.writeText(text).then(function() {
        var btn = document.querySelector('[data-copy="' + id + '"]');
        var orig = btn.textContent;
        btn.textContent = 'Copied';
        setTimeout(function() { btn.textContent = orig; }, 2000);
    });
}
function getTheme() {
    return localStorage.getItem('theme') || 'auto';
}
function applyTheme(theme) {
    var root = document.documentElement;
    if (theme === 'auto') {
        root.removeAttribute('data-theme');
    } else {
        root.setAttribute('data-theme', theme);
    }
    updateToggleIcon();
}
function toggleTheme() {
    var current = getTheme();
    var next = current === 'auto' ? 'dark' : current === 'dark' ? 'light' : 'auto';
    localStorage.setItem('theme', next);
    applyTheme(next);
}
function updateToggleIcon() {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    var theme = getTheme();
    if (theme === 'dark') btn.textContent = '\\u263D';
    else if (theme === 'light') btn.textContent = '\\u2600';
    else btn.textContent = '\\u25D0';
    btn.title = 'Theme: ' + theme + ' (click to toggle)';
}
applyTheme(getTheme());
"""

def render(content):
    brand = get_brand()
    config = BRAND_CONFIG[brand]
    brand_label = f"{config['region_name']} {config['brand_name']}"
    # Support HA Ingress: X-Ingress-Path header sets the base path
    ingress_path = request.headers.get("X-Ingress-Path", "")
    return f"""<!DOCTYPE html>
<html lang="de"><head>
<title>Bluelink Token Generator</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<style>{STYLE}</style></head><body>
<script>var BASE_PATH = '{ingress_path}'; function bp(p){{return BASE_PATH+p;}}</script>
<div class="header"><div class="header-inner">
<h1>Bluelink Token Generator</h1>
<span class="brand">{brand_label}</span>
<button class="theme-toggle" id="theme-toggle" onclick="toggleTheme()" aria-label="Toggle theme">&#x25D0;</button>
</div></div>
<div class="container">{content}</div>
<div style="text-align:center;padding:16px;color:var(--text-secondary);font-size:12px;">
Bluelink Token Generator v{VERSION}</div>
<script>{SCRIPT}</script></body></html>"""

def get_brand():
    override = state.get("brand_override")
    if override and override in BRAND_CONFIG:
        return override
    brand = os.environ.get("BRAND", "auto").lower()
    # Resolve legacy aliases
    brand = BRAND_ALIASES.get(brand, brand)
    if brand in BRAND_CONFIG:
        return brand
    # "auto" or unknown → default to eu_hyundai
    return "eu_hyundai"

def log(msg, level="info"):
    state["log"].append((level, msg))
    print(f"[{level.upper()}] {msg}")

def format_log():
    lines = []
    for level, msg in state["log"]:
        cls = {"ok": "ok", "warn": "warn", "err": "err"}.get(level, "")
        escaped = html_lib.escape(msg)
        lines.append(f'<span class="{cls}">{escaped}</span>' if cls else escaped)
    return "<br>".join(lines)

TOKEN_EXPIRY_DAYS = 180

def _vehicle_key(brand, username):
    """Generate a unique key for a vehicle based on brand + username."""
    import hashlib
    return f"{brand}_{hashlib.md5(username.encode()).hexdigest()[:8]}"


def update_ha_sensor(brand, username="", days_remaining=None):
    """Create/update a Home Assistant sensor with the token expiry date (per vehicle)."""
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        return
    try:
        now = datetime.now(timezone.utc)
        if days_remaining is not None:
            # When refreshing an existing sensor, read the stored expiry date
            # instead of recalculating from days_remaining (avoids daily drift)
            vkey = _vehicle_key(brand, username)
            sensor_id = f"sensor.bluelink_token_expiry_{vkey}"
            existing_expiry = None
            try:
                resp = req_lib.get(
                    f"http://supervisor/core/api/states/{sensor_id}",
                    headers={"Authorization": f"Bearer {supervisor_token}"}, timeout=3)
                if resp.status_code == 200:
                    existing_state = resp.json().get("state", "")
                    if existing_state and existing_state not in ("unknown", "unavailable"):
                        existing_expiry = existing_state
            except Exception:
                pass
            if existing_expiry:
                # Re-publish the existing expiry date as-is (no drift)
                from datetime import date
                expiry_date = date.fromisoformat(existing_expiry)
                remaining = (expiry_date - date.today()).days
                expiry = datetime(expiry_date.year, expiry_date.month, expiry_date.day, tzinfo=timezone.utc)
            else:
                # No existing sensor — calculate from days_remaining
                expiry = now + timedelta(days=days_remaining)
                remaining = days_remaining
        else:
            # Fresh token generation — calculate new expiry
            expiry = now + timedelta(days=TOKEN_EXPIRY_DAYS)
            remaining = TOKEN_EXPIRY_DAYS
        headers = {
            "Authorization": f"Bearer {supervisor_token}",
            "Content-Type": "application/json",
        }
        brand_name = BRAND_CONFIG.get(brand, {}).get("brand_name", brand)
        vkey = _vehicle_key(brand, username)
        sensor_id = f"sensor.bluelink_token_expiry_{vkey}"
        masked_user = f"{username[:3]}***" if username else ""
        sensor_data = {
            "state": expiry.strftime("%Y-%m-%d"),
            "attributes": {
                "friendly_name": f"Bluelink Token ({brand_name} {masked_user})",
                "device_class": "date",
                "icon": "mdi:key-clock",
                "generated": (expiry - timedelta(days=TOKEN_EXPIRY_DAYS)).strftime("%Y-%m-%d %H:%M"),
                "expires": expiry.strftime("%Y-%m-%d %H:%M"),
                "days_remaining": remaining,
                "brand": brand,
                "username": username,
            },
        }
        resp = req_lib.post(
            f"http://supervisor/core/api/states/{sensor_id}",
            headers=headers, json=sensor_data, timeout=10)
        if resp.status_code in (200, 201):
            log(f"HA sensor updated ({sensor_id}).", "ok")
        else:
            log(f"Could not update HA sensor ({resp.status_code}).", "warn")
    except Exception as e:
        log(f"Could not update HA sensor: {e}", "warn")


def _save_token_timestamp(brand, username=""):
    """Save token generation timestamp per vehicle for Docker expiry check."""
    try:
        os.makedirs("/data", exist_ok=True)
        vkey = _vehicle_key(brand, username)
        with open(f"/data/token_generated_{vkey}.txt", "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())
    except Exception:
        pass


def _check_token_expiry(brand, username=""):
    """Check if token for a specific vehicle is still valid. Returns days_left or None."""
    vkey = _vehicle_key(brand, username)
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if supervisor_token:
        try:
            sensor_id = f"sensor.bluelink_token_expiry_{vkey}"
            resp = req_lib.get(
                f"http://supervisor/core/api/states/{sensor_id}",
                headers={"Authorization": f"Bearer {supervisor_token}"}, timeout=3)
            if resp.status_code == 200:
                expiry_str = resp.json().get("state", "")
                if expiry_str and expiry_str not in ("unknown", "unavailable"):
                    from datetime import date
                    return (date.fromisoformat(expiry_str) - date.today()).days
        except Exception:
            pass
    # Fallback: file-based
    try:
        with open(f"/data/token_generated_{vkey}.txt") as f:
            generated = datetime.fromisoformat(f.read().strip())
            return (generated + timedelta(days=TOKEN_EXPIRY_DAYS) - datetime.now(timezone.utc)).days
    except Exception:
        pass
    return None

# ── Routes ──────────────────────────────────────────────────

@app.route("/")
def index():
    brand = get_brand()
    config = BRAND_CONFIG[brand]
    bt = f"{config['region_name']} {config['brand_name']}"
    s = state["status"]

    if s == "idle":
        # Build vehicle forms from config or show empty form
        configured_vehicles = _get_vehicles_config()
        error_html = f'<div class="notice notice-error">{html_lib.escape(state.get("error", ""))}</div>' if state.get("error") else ""
        log_html = f'<details open><summary>Log</summary><div class="log">{format_log()}</div></details>' if state.get("log") else ""

        vehicles_html = ""
        if configured_vehicles:

            for i, v in enumerate(configured_vehicles):
                if not isinstance(v, dict):
                    continue
                b = v.get("brand", "eu_kia")
                bname = BRAND_CONFIG.get(b, {}).get("brand_name", b)
                days_left = _check_token_expiry(b, v.get('username', ''))
                if days_left is not None and days_left > 14:
                    expiry_badge = f'<span style="color:var(--success);font-size:12px;font-weight:bold;">✅ {days_left} days remaining</span>'
                elif days_left is not None:
                    expiry_badge = f'<span style="color:var(--warning);font-size:12px;font-weight:bold;">⚠ {days_left} days remaining</span>'
                else:
                    expiry_badge = '<span style="color:var(--text-secondary);font-size:12px;">No token yet</span>'
                vehicles_html += f"""
            <div style="border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="font-weight:bold;">{html_lib.escape(bname)} — {html_lib.escape(v.get('username', ''))}</div>
                    {expiry_badge}
                </div>
            </div>"""
            return render(f"""
<div class="card">
    <div class="card-title">Generate Refresh Tokens</div>
    <p style="margin-bottom:16px;color:var(--text-secondary);font-size:14px;">
        {len(configured_vehicles)} vehicle(s) configured.
    </p>
    {vehicles_html}
    <div class="actions">
        <button class="btn btn-primary" id="ql-btn" onclick="generateAll(false)">Generate All Tokens</button>
        <button class="btn btn-secondary" onclick="generateAll(true)">Force Renew</button>
    </div>
    <div id="ql-result" style="margin-top:12px;">{error_html}</div>
    <div id="ql-log" style="margin-top:12px;">{log_html}</div>
</div>
<hr class="divider">
<div class="card">
    <div class="card-title">Manual Login</div>
    <p style="margin-bottom:12px;color:var(--text-secondary);font-size:14px;">
        Or generate a token for a single vehicle manually.
    </p>
    <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:16px;">
        <select id="man-brand" style="padding:10px 14px;border:1px solid var(--border);border-radius:10px;font-size:14px;">
            <option value="eu_kia">Kia</option>
            <option value="eu_hyundai">Hyundai</option>
        </select>
        <input type="text" id="man-user" placeholder="E-Mail / Username" required>
        <input type="password" id="man-pass" placeholder="Password" required>
    </div>
    <button class="btn btn-secondary" onclick="generateSingle()">Generate Token</button>
</div>
<script>
function generateAll(force) {{
    var btn = document.getElementById('ql-btn');
    btn.disabled = true; btn.textContent = 'Generating...';
    document.getElementById('ql-result').innerHTML = '<div class="notice notice-info">Generating tokens for all vehicles...</div>';
    fetch(bp('/api/quicklogin'), {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{mode: 'all', force: !!force}})
    }}).then(function() {{ location.href = bp("/"); }}).catch(function() {{ location.href = bp("/"); }});
}}
function generateSingle() {{
    document.getElementById('ql-result').innerHTML = '<div class="notice notice-info">Generating token...</div>';
    fetch(bp('/api/quicklogin'), {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
            username: document.getElementById('man-user').value,
            password: document.getElementById('man-pass').value,
            brand: document.getElementById('man-brand').value
        }})
    }}).then(function() {{ location.href = bp("/"); }}).catch(function() {{ location.href = bp("/"); }});
}}
</script>""")
        else:
            # No vehicles configured — show dynamic multi-vehicle form
            return render(f"""
<div class="card">
    <div class="card-title">Generate Refresh Tokens</div>
    <p style="margin-bottom:16px;color:var(--text-secondary);font-size:14px;">
        Add your vehicles and generate tokens. You can add multiple vehicles at once.
    </p>
    <div id="vehicle-list"></div>
    <button class="btn btn-secondary" onclick="addVehicle()" style="margin-bottom:16px;">+ Add Vehicle</button>
    <br>
    <button class="btn btn-primary" id="ql-btn" onclick="generateAll()">Generate All Tokens</button>
    <div id="ql-result" style="margin-top:12px;">{error_html}</div>
    <div id="ql-log" style="margin-top:12px;">{log_html}</div>
</div>
<script>
var vehicleCount = 0;
function addVehicle() {{
    vehicleCount++;
    var div = document.createElement('div');
    div.id = 'vehicle-' + vehicleCount;
    div.style.cssText = 'border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:10px;position:relative;';
    div.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">' +
        '<span style="font-weight:bold;font-size:13px;">Vehicle ' + vehicleCount + '</span>' +
        '<button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:var(--error);cursor:pointer;font-size:16px;">✕</button></div>' +
        '<div style="display:flex;flex-direction:column;gap:8px;">' +
        '<select class="v-brand" style="padding:10px 14px;border:1px solid var(--border);border-radius:10px;font-size:14px;">' +
        '<option value="eu_kia">Kia</option><option value="eu_hyundai">Hyundai</option></select>' +
        '<input type="text" class="v-user" placeholder="E-Mail / Username" style="padding:10px 14px;border:1px solid var(--border);border-radius:10px;font-size:14px;">' +
        '<input type="password" class="v-pass" placeholder="Password" style="padding:10px 14px;border:1px solid var(--border);border-radius:10px;font-size:14px;">' +
        '</div>';
    document.getElementById('vehicle-list').appendChild(div);
}}
function generateAll() {{
    var vehicles = [];
    document.querySelectorAll('#vehicle-list > div').forEach(function(div) {{
        var brand = div.querySelector('.v-brand').value;
        var user = div.querySelector('.v-user').value;
        var pass = div.querySelector('.v-pass').value;
        if (user && pass) vehicles.push({{brand: brand, username: user, password: pass}});
    }});
    if (vehicles.length === 0) {{ document.getElementById('ql-result').innerHTML = '<div class="notice notice-warning">Add at least one vehicle.</div>'; return; }}
    var btn = document.getElementById('ql-btn');
    btn.disabled = true; btn.textContent = 'Generating...';
    document.getElementById('ql-result').innerHTML = '<div class="notice notice-info">Generating tokens...</div>';
    fetch(bp('/api/quicklogin'), {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{mode: 'list', vehicles: vehicles}})
    }}).then(function() {{ location.href = bp("/"); }}).catch(function() {{ location.href = bp("/"); }});
}}
addVehicle(); // Start with one vehicle form
</script>""")

    elif s == "processing":
        return render(f"""
<div class="card">
    <div class="card-title">Processing</div>
    <div class="notice notice-info">Generating token...</div>
    <div class="log" id="log-box">{format_log()}</div>
</div>
<script>
(function poll() {{
    fetch(bp('/api/status')).then(function(r){{ return r.json(); }}).then(function(d) {{
        if (d.log) document.getElementById('log-box').innerHTML = d.log;
        if (d.status !== 'processing') {{
            setTimeout(function(){{ window.location = bp('/'); }}, 500);
        }} else {{
            setTimeout(poll, 1500);
        }}
    }}).catch(function(){{ setTimeout(poll, 2000); }});
}})();
</script>""")

    elif s == "success":
        # Show tokens for all vehicles
        vehicles = state.get("vehicles", [])
        tokens_html = ""
        if vehicles:
            for i, v in enumerate(vehicles):
                if v.get("status") == "ok":
                    rt = html_lib.escape(v.get("refresh_token", ""))
                    tokens_html += f"""
    <div style="margin: 16px 0; border: 1px solid var(--border); border-radius: 10px; padding: 16px;">
        <div class="token-label">{html_lib.escape(v.get('brand_name', ''))} — {html_lib.escape(v.get('username', '')[:3])}***</div>
        <div class="token-box" id="refresh-{i}">{rt}</div>
        <button class="copy-link" data-copy="refresh-{i}" onclick="copyToken('refresh-{i}')">Copy to clipboard</button>
    </div>"""
                else:
                    tokens_html += f"""
    <div style="margin: 16px 0; border: 1px solid var(--error); border-radius: 10px; padding: 16px;">
        <div class="token-label" style="color:var(--error);">{html_lib.escape(v.get('brand_name', ''))} — Failed</div>
        <div style="color:var(--error);font-size:13px;">{html_lib.escape(v.get('error', 'unknown'))}</div>
    </div>"""
        else:
            # Legacy single token
            rt = html_lib.escape(state.get("refresh_token", ""))
            tokens_html = f"""
    <div style="margin: 20px 0;">
        <div class="token-label">Refresh Token</div>
        <div class="token-box" id="refresh-0">{rt}</div>
        <button class="copy-link" data-copy="refresh-0" onclick="copyToken('refresh-0')">Copy to clipboard</button>
    </div>"""

        tr = state.get("test_result", "")
        test_html = ""
        if tr == "ok":
            test_html = '<div class="notice notice-success">Token verified — API connection successful.</div>'
        elif tr:
            test_html = f'<div class="notice notice-error">Verification failed: {html_lib.escape(tr)}</div>'
        evcc_configured = bool(os.environ.get("EVCC_URL"))
        if evcc_configured:
            evcc_fields_html = '<div class="notice notice-info" style="margin-bottom:12px;">evcc connection configured via addon settings.</div>'
        else:
            evcc_fields_html = """
    <div style="margin-bottom: 12px;">
        <div class="section-label">evcc URL</div>
        <input type="text" id="evcc-url-input" placeholder="http://192.168.1.100:7070" style="
            width: 100%; padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px;
            font-size: 14px; font-family: inherit;"
            oninput="document.getElementById('evcc-url').value=this.value">
    </div>
    <div style="margin-bottom: 12px;">
        <div class="section-label">evcc Admin Password</div>
        <input type="password" id="evcc-password-input" placeholder="Admin password (leave empty if not set)" style="
            width: 100%; padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px;
            font-size: 14px; font-family: inherit;"
            oninput="document.getElementById('evcc-password').value=this.value">
    </div>"""
        return render(f"""
<div class="card">
    <div class="card-title">Token generated</div>
    <div class="notice notice-success">Token(s) generated successfully.</div>
    {test_html}
    {tokens_html}
    <div class="notice notice-warning">
        This token is valid for 180 days (expires {(datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS)).strftime('%B %d, %Y')}). After that you will need to generate a new one.
    </div>
    <hr class="divider">
    <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 16px;">
        Use this refresh token as the password together with your regular username
        when configuring the evcc or Home Assistant integration.
    </p>
    <div class="actions">
        <form method="POST" action="" onsubmit="event.preventDefault();fetch(bp('/test'),{{method:'POST'}}).then(function(){{location.href=bp('/')}})" style="margin:0;">
            <button type="submit" class="btn btn-secondary">Verify token</button>
        </form>
        <form method="POST" action="" onsubmit="event.preventDefault();fetch(bp('/reset'),{{method:'POST'}}).then(function(){{location.href=bp('/')}})" style="margin:0;">
            <button type="submit" class="btn btn-danger">Reset</button>
        </form>
    </div>
    <hr class="divider">
    <details><summary>Show log</summary><div class="log">{format_log()}</div></details>
</div>
<div class="card">
    <div class="card-title">Send to evcc</div>
    <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 16px;">
        Transfer the refresh token directly to an evcc instance in your network.
    </p>
    <input type="hidden" id="evcc-url" value="{html_lib.escape(os.environ.get('EVCC_URL', ''))}">
    <input type="hidden" id="evcc-password" value="{html_lib.escape(os.environ.get('EVCC_PASSWORD', ''))}">
    {evcc_fields_html}
    {"" if evcc_configured else '<button class="btn btn-secondary" onclick="evccLoadVehicles()" id="evcc-connect-btn">Connect</button>'}
    <div id="evcc-vehicles" style="display:none; margin-top: 16px;">
        <div class="section-label">Vehicles</div>
        <div id="evcc-vehicle-list" style="margin-bottom: 12px;"></div>
        <button class="btn btn-primary" onclick="evccSendToken()">Send token to selected vehicles</button>
    </div>
    <div id="evcc-result" style="margin-top: 12px;"></div>
</div>
<script>
var evccVehicles = [];
function evccLoadVehicles() {{
    var url = document.getElementById('evcc-url').value;
    var pw = document.getElementById('evcc-password').value;
    var btn = document.getElementById('evcc-connect-btn');
    var resultDiv = document.getElementById('evcc-result');
    if (btn) {{ btn.textContent = 'Connecting...'; btn.disabled = true; }}
    resultDiv.innerHTML = '';
    fetch(bp('/api/evcc/vehicles'), {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{url: url, password: pw}})
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
        if (btn) {{ btn.textContent = 'Connect'; btn.disabled = false; }}
        if (!d.ok) {{ resultDiv.innerHTML = '<div class="notice notice-error">' + d.error + '</div>'; return; }}
        if (d.vehicles.length === 0) {{ resultDiv.innerHTML = '<div class="notice notice-warning">No Hyundai/Kia vehicles found in evcc.</div>'; return; }}
        evccVehicles = d.vehicles;
        if (d.vehicles.length === 1) {{
            resultDiv.innerHTML = '<div class="notice notice-info">Found ' + d.vehicles[0].title + ' — sending token...</div>';
            evccSendToVehicles([d.vehicles[0].id]);
        }} else {{
            var listDiv = document.getElementById('evcc-vehicle-list');
            listDiv.innerHTML = '';
            d.vehicles.forEach(function(v) {{
                var label = document.createElement('label');
                label.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 12px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;cursor:pointer;';
                var cb = document.createElement('input');
                cb.type = 'checkbox'; cb.value = v.id; cb.checked = true;
                cb.style.cssText = 'width:18px;height:18px;';
                label.appendChild(cb);
                label.appendChild(document.createTextNode(v.title + ' (' + v.template + ')'));
                listDiv.appendChild(label);
            }});
            document.getElementById('evcc-vehicles').style.display = 'block';
            resultDiv.innerHTML = '<div class="notice notice-success">Connected — ' + d.vehicles.length + ' vehicles found. All selected by default.</div>';
        }}
    }}).catch(function(e) {{ if (btn) {{ btn.textContent = 'Connect'; btn.disabled = false; }} resultDiv.innerHTML = '<div class="notice notice-error">Connection failed: ' + e + '</div>'; }});
}}
function evccSendToken() {{
    var checkboxes = document.querySelectorAll('#evcc-vehicle-list input[type=checkbox]:checked');
    var ids = Array.from(checkboxes).map(function(cb) {{ return parseInt(cb.value); }});
    if (ids.length === 0) {{ document.getElementById('evcc-result').innerHTML = '<div class="notice notice-warning">No vehicles selected.</div>'; return; }}
    evccSendToVehicles(ids);
}}
function evccSendToVehicles(ids) {{
    var url = document.getElementById('evcc-url').value;
    var pw = document.getElementById('evcc-password').value;
    var resultDiv = document.getElementById('evcc-result');
    var total = ids.length, done = 0, errors = [];
    resultDiv.innerHTML = '<div class="notice notice-info">Sending token to ' + total + ' vehicle(s)...</div>';
    ids.forEach(function(vid) {{
        fetch(bp('/api/evcc/update'), {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{url: url, password: pw, vehicle_id: vid}})
        }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
            if (!d.ok) errors.push(d.error);
            done++;
            if (done === total) evccTransferDone(total, errors);
        }}).catch(function(e) {{ errors.push(String(e)); done++; if (done === total) evccTransferDone(total, errors); }});
    }});
}}
function evccTransferDone(total, errors) {{
    var resultDiv = document.getElementById('evcc-result');
    var ok = total - errors.length;
    if (errors.length === 0) {{
        resultDiv.innerHTML = '<div class="notice notice-success">Token sent to ' + ok + ' vehicle(s) — restarting evcc...</div>';
        evccRestart();
    }} else if (ok > 0) {{
        resultDiv.innerHTML = '<div class="notice notice-warning">Token sent to ' + ok + '/' + total + ' vehicle(s). Errors: ' + errors.join(', ') + '</div><div class="notice notice-info" style="margin-top:8px;">Restarting evcc...</div>';
        evccRestart();
    }} else {{
        resultDiv.innerHTML = '<div class="notice notice-error">Transfer failed: ' + errors.join(', ') + '</div>';
    }}
}}
function evccRestart() {{
    var url = document.getElementById('evcc-url').value;
    var pw = document.getElementById('evcc-password').value;
    var resultDiv = document.getElementById('evcc-result');
    fetch(bp('/api/evcc/restart'), {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{url: url, password: pw}})
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
        if (d.ok) {{ evccDone('<div class="notice notice-success">Token transferred and evcc restarted successfully!</div>'); }}
        else {{ evccDone('<div class="notice notice-success">Token transferred.</div><div class="notice notice-warning" style="margin-top:8px;">Could not restart evcc automatically: ' + d.error + '. Please restart evcc manually.</div>'); }}
    }}).catch(function(e) {{ evccDone('<div class="notice notice-success">Token transferred.</div><div class="notice notice-warning" style="margin-top:8px;">Could not restart evcc automatically. Please restart evcc manually.</div>'); }});
}}
function evccDone(msg) {{
    var resultDiv = document.getElementById('evcc-result');
    resultDiv.innerHTML = msg;
}}
{"// Auto-connect if evcc is configured\nwindow.addEventListener('load', function() { document.getElementById('evcc-result').innerHTML = '<div class=\"notice notice-info\">Connecting to evcc...</div>'; evccLoadVehicles(); });" if evcc_configured else ""}
</script>
{_render_kia_uvo_card()}
""")

    elif s == "error":
        err = html_lib.escape(state.get("error", "Unknown error"))
        return render(f"""
<div class="card">
    <div class="card-title">Error</div>
    <div class="notice notice-error">{err}</div>
    <details open><summary>Log</summary><div class="log">{format_log()}</div></details>
    <hr class="divider">
    <form method="POST" action="" onsubmit="event.preventDefault();fetch(bp('/reset'),{{method:'POST'}}).then(function(){{location.href=bp('/')}})">
        <button type="submit" class="btn btn-danger">Reset</button>
    </form>
</div>""")

    return render('<div class="card">Unknown state</div>')

@app.route("/reset", methods=["POST"])
def reset():
    state.update({"status": "idle", "refresh_token": None, "access_token": None,
                  "error": None, "test_result": "", "log": [], "brand_override": None,
                  "vehicles": []})
    _cancel_auto_reset()
    return flask_redirect("/")


_auto_reset_timer = {"timer": None}


def _cancel_auto_reset():
    """Cancel any pending auto-reset timer."""
    if _auto_reset_timer["timer"]:
        _auto_reset_timer["timer"].cancel()
        _auto_reset_timer["timer"] = None


def _schedule_auto_reset():
    """Schedule auto-reset after 5 minutes if no API_TOKEN is configured."""
    api_token = os.environ.get("API_TOKEN", "").strip()
    if api_token:
        return  # API_TOKEN set → keep tokens available permanently
    _cancel_auto_reset()

    def do_reset():
        state.update({"status": "idle", "refresh_token": None, "access_token": None,
                      "error": None, "test_result": "", "log": [], "brand_override": None,
                      "vehicles": []})
        print("[AUTO] Token cleared from memory after 5 minutes.", flush=True)

    _auto_reset_timer["timer"] = threading.Timer(300, do_reset)
    _auto_reset_timer["timer"].daemon = True
    _auto_reset_timer["timer"].start()

@app.route("/test", methods=["POST"])
def test_token():
    brand = get_brand()
    config = BRAND_CONFIG[brand]
    refresh_token = state.get("refresh_token")
    if not refresh_token:
        state["test_result"] = "No refresh token available."
        return flask_redirect("/")
    try:
        data = {"grant_type": "refresh_token", "refresh_token": refresh_token,
                "client_id": config["client_id"], "client_secret": config["client_secret"]}
        response = req_lib.post(config["token_url"], data=data, timeout=10)
        if response.status_code == 200:
            new_tokens = response.json()
            if new_tokens.get("access_token"):
                state["access_token"] = new_tokens["access_token"]
                state["test_result"] = "ok"
            else:
                state["test_result"] = "No access token in response"
        else:
            state["test_result"] = f"Token refresh failed ({response.status_code}): {response.text[:150]}"
    except Exception as e:
        state["test_result"] = str(e)
    return flask_redirect("/")

@app.route("/api/quicklogin", methods=["POST"])
def api_quicklogin():
    """Headless login — single vehicle or all configured vehicles."""
    data = request.get_json()
    mode = data.get("mode", "single")

    if mode == "all":
        # Generate tokens for all configured vehicles
        force = data.get("force", False)
        threading.Thread(target=lambda: _auto_start_login(force=force), daemon=True).start()
        return jsonify({"ok": True, "message": "Generating tokens for all vehicles..."})

    if mode == "list":
        # Generate tokens for a list of vehicles from the UI
        vehicles = data.get("vehicles", [])
        if not vehicles:
            return jsonify({"ok": False, "error": "No vehicles provided"})
        os.environ["_TEMP_VEHICLES"] = json.dumps(vehicles)
        threading.Thread(target=lambda: _auto_start_login(force=True), daemon=True).start()
        return jsonify({"ok": True})

    # Single vehicle login
    username = data.get("username", "")
    password = data.get("password", "")
    chosen_brand = data.get("brand", "").lower()
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"})

    chosen_brand = BRAND_ALIASES.get(chosen_brand, chosen_brand)
    if chosen_brand not in BRAND_CONFIG:
        chosen_brand = "eu_kia"
    state["brand_override"] = chosen_brand
    config = BRAND_CONFIG[chosen_brand]

    state["status"] = "processing"
    state["log"] = []
    state["vehicles"] = []
    log(f"Quick login: starting for {config['region_name']} {config['brand_name']}...")

    try:
        result = _headless_login_eu_with_retry(username, password, config)
        if result.get("ok"):
            return jsonify({"ok": True})
        else:
            err = result.get("error", "Login failed")
            state["status"] = "idle"
            state["error"] = err
            log(err, "err")
            return jsonify({"ok": False, "error": err})
    except Exception as e:
        state["status"] = "idle"
        state["error"] = str(e)
        log(str(e), "err")
        return jsonify({"ok": False, "error": str(e)})

def _headless_login_eu_with_retry(username, password, config, max_retries=2):
    """Wrapper around _headless_login_eu with retry logic for transient failures."""
    last_result = None
    for attempt in range(1, max_retries + 2):  # 1 initial + max_retries
        result = _headless_login_eu(username, password, config)
        if result.get("ok"):
            return result
        last_result = result
        error = result.get("error", "")
        # Don't retry on credential errors or password issues
        if any(x in error.lower() for x in ("password", "username", "credentials", "rejected", "login page")):
            return result
        if attempt <= max_retries:
            wait = attempt * 5  # 5s, 10s
            log(f"Headless: attempt {attempt} failed ({error}), retrying in {wait}s...", "warn")
            time.sleep(wait)
    return last_result


def _send_webhook(event, data=None):
    """Send a webhook notification if WEBHOOK_URL is configured.
    
    Events: token_generated, token_failed, token_renewed
    """
    webhook_url = os.environ.get("WEBHOOK_URL", "").strip()
    if not webhook_url:
        return
    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data or {},
    }
    try:
        resp = req_lib.post(webhook_url, json=payload, timeout=10)
        if resp.status_code < 300:
            log(f"Webhook sent ({event}).", "ok")
        else:
            log(f"Webhook failed ({resp.status_code}).", "warn")
    except Exception as e:
        log(f"Webhook error: {e}", "warn")


def _send_ha_notification(title, message):
    """Send a persistent notification via HA if running as addon."""
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        return
    try:
        req_lib.post(
            "http://supervisor/core/api/services/persistent_notification/create",
            headers={"Authorization": f"Bearer {supervisor_token}", "Content-Type": "application/json"},
            json={"title": title, "message": message, "notification_id": "bluelink_token"},
            timeout=5)
    except Exception:
        pass


def _headless_login_eu(username, password, config):
    """
    Headless EU Kia/Hyundai login using curl_cffi (Android TLS fingerprint).
    No browser needed — pure HTTP requests.

    Flow:
      1. GET authorize page (get cookies)
      2. GET /auth/api/v1/accounts/certs (RSA public key)
      3. POST /auth/account/signin with encrypted password + app client_id
         → 302 redirect with code directly
      4. POST token exchange → refresh + access token
    """
    # Derive host from token_url
    from urllib.parse import urlparse as _urlparse
    host = f"{_urlparse(config['token_url']).scheme}://{_urlparse(config['token_url']).netloc}"
    client_id = config["client_id"]
    redirect_uri = config["redirect_url_final"]

    log("Headless login: starting (curl_cffi, Android TLS fingerprint)...", "ok")

    s = curl_requests.Session(impersonate="chrome131_android")
    s.headers.update({"User-Agent": config["user_agent"]})

    # Step 1: Load authorize page to get session cookies
    log(f"Headless: loading authorize page ({host})...")
    auth_url = (f"{host}/auth/api/v2/user/oauth2/authorize"
                f"?response_type=code&client_id={client_id}"
                f"&redirect_uri={redirect_uri}&lang=de&state=ccsp&country=de")
    resp = s.get(auth_url, allow_redirects=True)
    log(f"Headless: authorize page loaded (HTTP {resp.status_code}, cookies: {list(s.cookies.keys())})")

    # Step 2: Get RSA public key for password encryption
    log("Headless: fetching RSA public key...")
    resp = s.get(f"{host}/auth/api/v1/accounts/certs")
    if resp.status_code != 200:
        return {"ok": False, "error": f"Certs endpoint returned {resp.status_code}"}
    jwk = resp.json().get("retValue", {})
    kid = jwk.get("kid", "")
    log(f"Headless: RSA key loaded (kid: {kid})")

    # Convert JWK to RSA key
    n_bytes = base64.urlsafe_b64decode(jwk["n"] + "==")
    e_bytes = base64.urlsafe_b64decode(jwk["e"] + "==")
    n = int.from_bytes(n_bytes, "big")
    e = int.from_bytes(e_bytes, "big")
    key = RSA.construct((n, e))
    cipher = PKCS1_v1_5.new(key)
    encrypted_pw = cipher.encrypt(password.encode("utf-8")).hex()

    # Validate password (Kia/Hyundai requirement: 8-20 chars, upper+lower+digit+special)
    pw_len = len(password)
    if pw_len < 8 or pw_len > 20:
        return {"ok": False, "error": f"Password must be 8-20 characters (yours: {pw_len}). "
                "Kia/Hyundai reject passwords outside this range."}
    pw_issues = []
    if not any(c.isupper() for c in password):
        pw_issues.append("uppercase letter")
    if not any(c.islower() for c in password):
        pw_issues.append("lowercase letter")
    if not any(c.isdigit() for c in password):
        pw_issues.append("digit")
    if not any(not c.isalnum() for c in password):
        pw_issues.append("special character")
    if pw_issues:
        log(f"Headless: password may not meet requirements (missing: {', '.join(pw_issues)})", "warn")

    # Step 3: POST signin with app client_id → code comes directly in redirect
    log(f"Headless: signing in as {username[:3]}***@{username.split('@')[-1] if '@' in username else '***'} (password length: {pw_len})...")
    resp = s.post(f"{host}/auth/account/signin", data={
        "client_id": client_id,
        "encryptedPassword": "true",
        "password": encrypted_pw,
        "redirect_uri": redirect_uri,
        "scope": "",
        "nonce": "",
        "state": "ccsp",
        "username": username,
        "connector_session_key": "",
        "kid": kid,
        "_csrf": "",
    }, allow_redirects=False)

    log(f"Headless: signin response HTTP {resp.status_code}")
    if resp.status_code != 302:
        return {"ok": False, "error": f"Signin returned HTTP {resp.status_code} (expected 302). Response: {resp.text[:300]}"}

    location = resp.headers.get("location", "")
    log(f"Headless: redirect → {location}")
    code_list = parse_qs(urlparse(location).query).get("code")
    if not code_list:
        if "error" in location.lower():
            error_desc = parse_qs(urlparse(location).query).get("error_description", ["unknown"])[0]
            return {"ok": False, "error": f"Signin rejected: {error_desc}"}
        if "authorize" in location:
            return {"ok": False, "error": "Signin failed — redirected back to login page. Please check username and password."}
        return {"ok": False, "error": f"No code in redirect: {location[:250]}"}

    code = code_list[0]
    log(f"Headless: authorization code received.", "ok")

    # Step 4: Token exchange
    log("Headless: exchanging code for tokens...")
    resp = curl_requests.post(config["token_url"], data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": config["client_secret"],
    })

    if resp.status_code != 200:
        return {"ok": False, "error": f"Token exchange failed: HTTP {resp.status_code}: {resp.text[:200]}"}

    tokens = resp.json()
    state["refresh_token"] = tokens.get("refresh_token", "N/A")
    state["access_token"] = tokens.get("access_token", "N/A")
    state["status"] = "success"
    log("Token generated successfully via headless login!", "ok")
    _schedule_auto_reset()
    # Determine brand from config for sensor/timestamp
    _brand = next((k for k, v in BRAND_CONFIG.items() if v.get("client_id") == config.get("client_id")), "eu_kia")
    update_ha_sensor(_brand, username)
    _save_token_timestamp(_brand, username)

    return {"ok": True, "message": "Login successful — tokens generated!"}

@app.route("/api/status")
def api_status():
    return jsonify({"status": state["status"], "log": format_log()})


@app.route("/health")
def health():
    """Healthcheck endpoint for Docker/orchestrators."""
    vehicles = _get_vehicles_config()
    return jsonify({
        "status": "ok",
        "version": VERSION,
        "vehicles_configured": len(vehicles),
    })


# ── Token API ───────────────────────────────────────────────

def _check_api_auth():
    """Check API_TOKEN authentication if configured. Returns error response or None."""
    api_token = os.environ.get("API_TOKEN", "").strip()
    if not api_token:
        return None  # No auth configured, allow access
    # Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        provided = auth_header[7:].strip()
        if provided == api_token:
            return None
    return jsonify({"ok": False, "error": "Unauthorized. Set Authorization: Bearer <API_TOKEN> header."}), 401


@app.route("/api/tokens", methods=["GET"])
def api_tokens_get():
    """Return current token state for all configured vehicles.
    
    Response:
      {
        "vehicles": [
          {
            "brand": "eu_kia",
            "brand_name": "Kia",
            "username": "user@example.com",
            "refresh_token": "...",
            "days_remaining": 165,
            "status": "valid" | "expiring" | "expired" | "unknown"
          }
        ]
      }
    """
    auth_error = _check_api_auth()
    if auth_error:
        return auth_error

    vehicles = _get_vehicles_config()
    result = []
    for v in vehicles:
        if not isinstance(v, dict):
            continue
        brand = BRAND_ALIASES.get(v.get("brand", ""), v.get("brand", ""))
        username = v.get("username", "")
        if brand not in BRAND_CONFIG or not username:
            continue
        config = BRAND_CONFIG[brand]
        days_left = _check_token_expiry(brand, username)
        # Check if we have a token in state
        token = None
        for sv in state.get("vehicles", []):
            if sv.get("brand") == brand and sv.get("username") == username and sv.get("status") == "ok":
                token = sv.get("refresh_token")
                break
        if days_left is not None and days_left > 14:
            status = "valid"
        elif days_left is not None and days_left > 0:
            status = "expiring"
        elif days_left is not None:
            status = "expired"
        else:
            status = "unknown"
        result.append({
            "brand": brand,
            "brand_name": config["brand_name"],
            "username": username,
            "refresh_token": token,
            "days_remaining": days_left,
            "status": status,
        })

    # If no API_TOKEN is configured, clear tokens after retrieval
    api_token = os.environ.get("API_TOKEN", "").strip()
    if not api_token and any(r.get("refresh_token") for r in result):
        _cancel_auto_reset()
        state.update({"status": "idle", "refresh_token": None, "access_token": None,
                      "error": None, "test_result": "", "log": [], "brand_override": None,
                      "vehicles": []})

    return jsonify({"vehicles": result})


@app.route("/api/tokens", methods=["POST"])
def api_tokens_generate():
    """Generate tokens for all configured vehicles or a single vehicle via credentials.
    
    Request body (optional):
      { "force": true }   — renew even if token is still valid
    
    Or provide credentials directly for a single vehicle:
      {
        "brand": "eu_kia",
        "username": "user@example.com",
        "password": "yourpassword"
      }
    
    Response:
      {
        "ok": true,
        "vehicles": [
          {
            "brand": "eu_kia",
            "brand_name": "Kia",
            "username": "user@example.com",
            "refresh_token": "...",
            "status": "ok" | "skipped" | "error",
            "message": "..."
          }
        ]
      }
    """
    auth_error = _check_api_auth()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    force = data.get("force", False)

    # If credentials are provided directly, use those for a single vehicle
    if data.get("username") and data.get("password"):
        brand = BRAND_ALIASES.get(data.get("brand", "eu_kia").lower(), data.get("brand", "eu_kia").lower())
        username = data["username"]
        password = data["password"]
        if brand not in BRAND_CONFIG:
            return jsonify({"ok": False, "error": f"Unknown brand: {brand}. Use 'eu_kia' or 'eu_hyundai'."}), 400
        config = BRAND_CONFIG[brand]
        try:
            result = _headless_login_eu_with_retry(username, password, config)
            if result.get("ok"):
                token = state.get("refresh_token")
                return jsonify({"ok": True, "vehicles": [{
                    "brand": brand, "brand_name": config["brand_name"],
                    "username": username, "status": "ok",
                    "refresh_token": token,
                    "message": "Token generated successfully",
                }]})
            else:
                return jsonify({"ok": False, "vehicles": [{
                    "brand": brand, "brand_name": config["brand_name"],
                    "username": username, "status": "error",
                    "message": result.get("error", "Login failed"),
                }]})
        except Exception as e:
            return jsonify({"ok": False, "vehicles": [{
                "brand": brand, "brand_name": config["brand_name"],
                "username": username, "status": "error",
                "message": str(e),
            }]})

    # Otherwise, generate for all configured vehicles
    vehicles = _get_vehicles_config()

    if not vehicles:
        return jsonify({"ok": False, "error": "No vehicles configured. Set VEHICLES_JSON or BRAND/BLUELINK_USERNAME/BLUELINK_PASSWORD env vars."}), 400

    results = []
    for i, v in enumerate(vehicles):
        if not isinstance(v, dict):
            continue
        brand = BRAND_ALIASES.get(v.get("brand", ""), v.get("brand", ""))
        username = v.get("username", "")
        password = v.get("password", "")
        if brand not in BRAND_CONFIG or not username or not password:
            results.append({"brand": brand, "username": username, "status": "error", "message": "Invalid config"})
            continue

        config = BRAND_CONFIG[brand]

        # Check expiry unless forced
        if not force:
            days_left = _check_token_expiry(brand, username)
            if days_left is not None and days_left > 14:
                # Return existing token if available
                existing_token = None
                for sv in state.get("vehicles", []):
                    if sv.get("brand") == brand and sv.get("username") == username and sv.get("status") == "ok":
                        existing_token = sv.get("refresh_token")
                        break
                results.append({
                    "brand": brand, "brand_name": config["brand_name"],
                    "username": username, "status": "skipped",
                    "refresh_token": existing_token,
                    "days_remaining": days_left,
                    "message": f"Token still valid ({days_left} days remaining)",
                })
                continue

        # Generate new token
        try:
            result = _headless_login_eu_with_retry(username, password, config)
            if result.get("ok"):
                token = state.get("refresh_token")
                # Store in vehicles state
                found = False
                for sv in state.get("vehicles", []):
                    if sv.get("brand") == brand and sv.get("username") == username:
                        sv["refresh_token"] = token
                        sv["status"] = "ok"
                        found = True
                        break
                if not found:
                    state.setdefault("vehicles", []).append({
                        "brand": brand, "brand_name": config["brand_name"],
                        "username": username, "refresh_token": token,
                        "access_token": state.get("access_token"), "status": "ok",
                    })
                results.append({
                    "brand": brand, "brand_name": config["brand_name"],
                    "username": username, "status": "ok",
                    "refresh_token": token,
                    "message": "Token generated successfully",
                })
            else:
                results.append({
                    "brand": brand, "brand_name": config["brand_name"],
                    "username": username, "status": "error",
                    "message": result.get("error", "Login failed"),
                })
        except Exception as e:
            results.append({
                "brand": brand, "brand_name": config["brand_name"],
                "username": username, "status": "error",
                "message": str(e),
            })

    has_error = any(r["status"] == "error" for r in results)
    return jsonify({"ok": not has_error, "vehicles": results})

# ── evcc Integration ────────────────────────────────────────

@app.route("/api/evcc/vehicles", methods=["POST"])
def evcc_vehicles():
    """Login to evcc and return list of Hyundai/Kia vehicles."""
    data = request.get_json()
    evcc_url = data.get("url", "").rstrip("/")
    password = data.get("password", "")
    return jsonify(evcc_get_vehicles(evcc_url, password))

@app.route("/api/evcc/update", methods=["POST"])
def evcc_update():
    """Update a vehicle's password (refresh token) in evcc."""
    data = request.get_json()
    evcc_url = data.get("url", "").rstrip("/")
    password = data.get("password", "")
    vehicle_id = data.get("vehicle_id")
    token = state.get("refresh_token")
    return jsonify(evcc_update_vehicle(evcc_url, password, vehicle_id, token))

@app.route("/api/evcc/restart", methods=["POST"])
def evcc_restart():
    """Restart evcc — via HA Supervisor API if available, otherwise via evcc shutdown."""
    data = request.get_json()
    evcc_url = data.get("url", "").rstrip("/")
    password = data.get("password", "")
    return jsonify(evcc_restart_impl(evcc_url, password))


# ── kia_uvo Integration ────────────────────────────────────────

@app.route("/api/kia_uvo/transfer", methods=["POST"])
def kia_uvo_transfer():
    """Manually trigger kia_uvo token transfer from the Web UI."""
    from kia_uvo import _auto_kia_uvo_transfer, _kia_uvo_config

    data = request.get_json(silent=True) or {}

    # Use provided values or fall back to _kia_uvo_config() (handles SUPERVISOR_TOKEN)
    ha_url = (data.get("ha_url") or "").strip().rstrip("/")
    ha_token = (data.get("ha_token") or "").strip()
    pin_override = (data.get("pin") or "").strip()

    # If no URL/token provided in request, use the module's config logic
    if not ha_url or not ha_token:
        config = _kia_uvo_config()
        if config:
            ha_url = config["ha_url"]
            ha_token = config["ha_token"]
        else:
            return jsonify({"ok": False, "error": "HA URL and Token are required."})

    # Check if we have generated tokens
    generated = [v for v in state.get("vehicles", []) if v.get("status") == "ok" and v.get("refresh_token")]
    if not generated:
        # Fallback: use the single token from state
        if state.get("refresh_token"):
            vehicles_config = _get_vehicles_config()
            username = vehicles_config[0].get("username", "") if vehicles_config else ""
            generated = [{"brand": "eu_kia", "username": username, "refresh_token": state["refresh_token"]}]
        else:
            return jsonify({"ok": False, "error": "No token generated yet. Generate a token first."})

    # Build vehicle list for kia_uvo transfer
    vehicles_config = _get_vehicles_config()
    kia_uvo_vehicles = []
    for sv in generated:
        orig = next((v for v in vehicles_config if v.get("username") == sv.get("username")), {})
        kia_uvo_vehicles.append({
            "brand": sv.get("brand", "eu_kia"),
            "username": sv.get("username", ""),
            "password": sv["refresh_token"],
            "pin": pin_override or orig.get("pin", "") or os.environ.get("HA_KIA_UVO_PIN", ""),
        })

    if not kia_uvo_vehicles:
        return jsonify({"ok": False, "error": "No vehicles with tokens available."})

    # Run the transfer (uses _kia_uvo_config() internally for auth)
    _auto_kia_uvo_transfer(kia_uvo_vehicles, log_fn=log)

    # Check if transfer succeeded by looking at the last log entry
    kia_uvo_logs = [(lvl, msg) for lvl, msg in state.get("log", []) if "kia_uvo:" in msg]
    if kia_uvo_logs:
        last_level, last_msg = kia_uvo_logs[-1]
        if last_level == "ok":
            return jsonify({"ok": True, "message": "Token transferred to kia_uvo successfully!"})
        elif last_level == "err":
            return jsonify({"ok": False, "error": last_msg.replace("kia_uvo: ", "")})
        elif last_level == "warn":
            return jsonify({"ok": False, "error": last_msg.replace("kia_uvo: ", "")})

    return jsonify({"ok": True, "message": "Transfer completed."})


def _auto_start_login(force=False):
    """Auto-start headless login for all configured vehicles."""
    import sys
    vehicles = _get_vehicles_config()
    # Check for temp vehicles from UI
    temp_vj = os.environ.pop("_TEMP_VEHICLES", "")
    if temp_vj:
        try:
            vehicles = json.loads(temp_vj)
            force = True  # UI-triggered = always generate
        except Exception:
            pass
    print(f"[AUTO] Found {len(vehicles)} vehicle(s) configured, force={force}", file=sys.stderr, flush=True)

    if not vehicles:
        print("[AUTO] No vehicles configured, skipping", file=sys.stderr, flush=True)
        return

    # Check token expiry per vehicle (unless force=True)
    state["status"] = "processing"
    state["log"] = []
    state["vehicles"] = []
    all_ok = True

    for i, v in enumerate(vehicles):
        if not isinstance(v, dict):
            log(f"Vehicle {i+1}: invalid format ({type(v).__name__}), skipping", "warn")
            continue
        brand = BRAND_ALIASES.get(v.get("brand", ""), v.get("brand", ""))
        username = v.get("username", "")
        password = v.get("password", "")
        if brand not in BRAND_CONFIG or not username or not password:
            log(f"Vehicle {i+1}: invalid config (brand={brand}), skipping", "warn")
            continue

        config = BRAND_CONFIG[brand]

        # Per-vehicle expiry check
        if not force:
            days_left = _check_token_expiry(brand, username)
            if days_left is not None and days_left > 14:
                log(f"Vehicle {i+1}: {config['brand_name']} — token still valid ({days_left} days). Skipping.", "ok")
                update_ha_sensor(brand, username, days_remaining=days_left)
                continue
            elif days_left is not None:
                log(f"Vehicle {i+1}: {config['brand_name']} — token expires in {days_left} days, renewing...")

        log(f"Vehicle {i+1}: {config['brand_name']} — logging in...")

        try:
            result = _headless_login_eu_with_retry(username, password, config)
            if result.get("ok"):
                log(f"Vehicle {i+1}: token generated!", "ok")
                state["vehicles"].append({
                    "brand": brand,
                    "brand_name": config["brand_name"],
                    "username": username,
                    "refresh_token": state["refresh_token"],
                    "access_token": state["access_token"],
                    "status": "ok",
                })
            else:
                log(f"Vehicle {i+1}: failed — {result.get('error', 'unknown')}", "err")
                state["vehicles"].append({
                    "brand": brand, "brand_name": config["brand_name"],
                    "username": username, "status": "error",
                    "error": result.get("error", "unknown"),
                })
                all_ok = False
        except Exception as e:
            log(f"Vehicle {i+1}: error — {e}", "err")
            all_ok = False

    if all_ok and state["vehicles"]:
        state["status"] = "success"
        log("Auto-start: all vehicles processed!", "ok")
        # Notify
        generated = [v for v in state["vehicles"] if v.get("status") == "ok"]
        if generated:
            _send_webhook("token_generated", {"vehicles": [{"brand": v["brand"], "username": v["username"]} for v in generated]})
            _send_ha_notification(
                "Bluelink Token Generated",
                f"Token(s) generated for {len(generated)} vehicle(s).")
        # Auto-transfer to evcc
        evcc_url = os.environ.get("EVCC_URL", "").rstrip("/")
        evcc_password = os.environ.get("EVCC_PASSWORD", "")
        if evcc_url:
            _auto_evcc_transfer(evcc_url, evcc_password)
        else:
            _schedule_auto_reset()

        # Auto-transfer to kia_uvo (independent of evcc)
        if _kia_uvo_transfer_enabled():
            try:
                # Build vehicle list with refresh tokens as passwords for kia_uvo
                # The reconfigure flow needs: username, password (=refresh_token), pin
                kia_uvo_vehicles = []
                for sv in state.get("vehicles", []):
                    if sv.get("status") == "ok" and sv.get("refresh_token"):
                        # Find original config to get pin
                        orig = next((v for v in vehicles if v.get("username") == sv.get("username")), {})
                        kia_uvo_vehicles.append({
                            "brand": sv.get("brand", ""),
                            "username": sv.get("username", ""),
                            "password": sv["refresh_token"],  # refresh token is the "password" for kia_uvo
                            "pin": orig.get("pin", ""),
                        })
                if kia_uvo_vehicles:
                    _auto_kia_uvo_transfer(kia_uvo_vehicles, log_fn=log)
            except Exception as e:
                print(f"[KIA_UVO] Transfer error (non-fatal): {e}", flush=True)
    elif state["vehicles"]:
        state["status"] = "success"  # partial success
        log("Auto-start: some vehicles failed, check log.", "warn")
        failed = [v for v in state["vehicles"] if v.get("status") == "error"]
        if failed:
            _send_webhook("token_failed", {"vehicles": [{"brand": v["brand"], "username": v["username"], "error": v.get("error", "")} for v in failed]})
            _send_ha_notification(
                "Bluelink Token Error",
                f"Token generation failed for {len(failed)} vehicle(s). Check the add-on log.")
        _schedule_auto_reset()
    else:
        state["status"] = "idle"
        log("Auto-start: no vehicles processed.", "warn")


def _kia_uvo_transfer_enabled():
    """Check if kia_uvo transfer is configured and enabled.

    Returns True if _kia_uvo_config() returns a non-None config dict,
    indicating that HA_URL and HA_TOKEN are set and transfer is not disabled.
    """
    return _kia_uvo_config() is not None


def _kia_uvo_auto_send_js(ha_configured, kia_uvo_logs):
    """Generate JS to auto-trigger kia_uvo transfer on page load if configured but not yet run."""
    if ha_configured and not kia_uvo_logs:
        return """window.addEventListener('load', function() {
    document.getElementById('kia-uvo-result').innerHTML = '<div class="notice notice-info">Transferring token to kia_uvo...</div>';
    kiaUvoSendToken();
});"""
    return ""


def _render_kia_uvo_card():
    """Render the kia_uvo transfer status card for the Web UI success page."""
    ha_url = os.environ.get("HA_URL", "").strip().rstrip("/")
    ha_token = os.environ.get("HA_TOKEN", "").strip()
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    ha_transfer_setting = os.environ.get("HA_KIA_UVO_TRANSFER", "").strip().lower()

    # Determine connection mode
    is_addon = bool(supervisor_token)
    ha_configured = is_addon or bool(ha_url and ha_token)

    # If explicitly disabled, don't show the card
    if ha_transfer_setting == "false":
        return ""

    # If not configured at all (standalone without HA settings), show input fields
    # If addon or configured, show status only

    # Find kia_uvo log entries from the current session
    kia_uvo_logs = [(lvl, msg) for lvl, msg in state.get("log", []) if "kia_uvo:" in msg]

    # Status badge
    if not kia_uvo_logs:
        status_html = ""
    else:
        last_level, last_msg = kia_uvo_logs[-1]
        if last_level == "ok" and "succeeded" in last_msg:
            status_html = '<div class="notice notice-success" style="margin-bottom:12px;">Token successfully transferred to kia_uvo integration.</div>'
        elif last_level == "ok" and "transferred" in last_msg.lower():
            status_html = '<div class="notice notice-success" style="margin-bottom:12px;">Token successfully transferred to kia_uvo integration.</div>'
        elif last_level == "err":
            status_html = '<div class="notice notice-error" style="margin-bottom:12px;">Transfer failed — check addon log for details.</div>'
        elif last_level == "warn":
            status_html = f'<div class="notice notice-warning" style="margin-bottom:12px;">{html_lib.escape(last_msg.replace("kia_uvo: ", ""))}</div>'
        else:
            status_html = ""

    # Input fields: only show when running standalone without any HA connection
    if is_addon:
        # Addon mode: no fields needed, SUPERVISOR_TOKEN handles everything
        fields_html = ""
    elif ha_configured:
        # Manual config via env vars
        fields_html = f"""
    <div style="margin-bottom: 12px;">
        <div class="section-label">Home Assistant URL</div>
        <div style="font-size: 13px; color: var(--text); padding: 8px 12px; background: var(--bg); border-radius: 8px; border: 1px solid var(--border);">
            {html_lib.escape(ha_url)}
        </div>
    </div>"""
    else:
        # Standalone mode: show input fields
        fields_html = """
    <div style="margin-bottom: 12px;">
        <div class="section-label">Home Assistant URL</div>
        <input type="text" id="kia-uvo-ha-url" placeholder="http://homeassistant.local:8123" style="
            width: 100%; padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px;
            font-size: 14px; font-family: inherit;">
    </div>
    <div style="margin-bottom: 12px;">
        <div class="section-label">Long-Lived Access Token</div>
        <input type="password" id="kia-uvo-ha-token" placeholder="HA Long-Lived Access Token" style="
            width: 100%; padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px;
            font-size: 14px; font-family: inherit;">
        <div class="hint">Create under HA → Profile → Security → Long-Lived Access Tokens</div>
    </div>
    <div style="margin-bottom: 12px;">
        <div class="section-label">Vehicle PIN (optional)</div>
        <input type="password" id="kia-uvo-pin" placeholder="Vehicle PIN" style="
            width: 100%; padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px;
            font-size: 14px; font-family: inherit;">
    </div>"""

    # Button: always show send button (for manual trigger or re-send)
    btn_html = f"""
    <button class="btn btn-{"secondary" if ha_configured else "primary"}" onclick="kiaUvoSendToken()" id="kia-uvo-send-btn">
        {"Re-send to kia_uvo" if kia_uvo_logs else "Send to kia_uvo"}
    </button>"""

    return f"""
<div class="card">
    <div class="card-title">Send to kia_uvo</div>
    <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 16px;">
        Transfer the refresh token to the kia_uvo Home Assistant integration via REST API.
    </p>
    {fields_html}
    {status_html}
    {btn_html}
    <div id="kia-uvo-result" style="margin-top: 12px;"></div>
</div>
<script>
function kiaUvoSendToken() {{
    var btn = document.getElementById('kia-uvo-send-btn');
    var resultDiv = document.getElementById('kia-uvo-result');
    btn.disabled = true; btn.textContent = 'Sending...';
    resultDiv.innerHTML = '<div class="notice notice-info">Transferring token to kia_uvo...</div>';
    var payload = {{}};
    var urlEl = document.getElementById('kia-uvo-ha-url');
    var tokenEl = document.getElementById('kia-uvo-ha-token');
    var pinEl = document.getElementById('kia-uvo-pin');
    if (urlEl) payload.ha_url = urlEl.value;
    if (tokenEl) payload.ha_token = tokenEl.value;
    if (pinEl) payload.pin = pinEl.value;
    fetch(bp('/api/kia_uvo/transfer'), {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(payload)
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
        btn.disabled = false; btn.textContent = 'Re-send to kia_uvo';
        if (d.ok) {{
            resultDiv.innerHTML = '<div class="notice notice-success">' + (d.message || 'Token transferred successfully!') + '</div>';
        }} else {{
            resultDiv.innerHTML = '<div class="notice notice-error">' + (d.error || 'Transfer failed') + '</div>';
        }}
    }}).catch(function(e) {{
        btn.disabled = false; btn.textContent = 'Re-send to kia_uvo';
        resultDiv.innerHTML = '<div class="notice notice-error">Connection error: ' + e + '</div>';
    }});
}}
{_kia_uvo_auto_send_js(ha_configured, kia_uvo_logs)}
</script>"""


def _auto_evcc_transfer(evcc_url, evcc_password):
    """Auto-transfer refresh token to evcc after successful login."""
    _auto_evcc_transfer_impl(evcc_url, evcc_password, state, log_fn=log)

# Auto-start on module load
def _schedule_auto_start():
    """Schedule auto-start with a small delay to let the server finish startup."""
    import sys
    print("[AUTO] Auto-start thread started, waiting 3s...", file=sys.stderr, flush=True)
    time.sleep(3)
    print("[AUTO] Running auto-start login...", file=sys.stderr, flush=True)
    _auto_start_login()

threading.Thread(target=_schedule_auto_start, daemon=True).start()
print("[AUTO] Auto-start thread scheduled", flush=True)


# Periodic HA sensor refresh (every 30 minutes)
def _sensor_refresh_loop():
    """Periodically re-publish HA sensors so they survive HA restarts."""
    import sys
    INTERVAL = 30 * 60  # 30 minutes
    time.sleep(INTERVAL)  # first run after 30 min (auto-start already sets it)
    while True:
        try:
            supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
            if not supervisor_token:
                break  # not running as HA addon, stop loop
            vehicles = _get_vehicles_config()
            for v in vehicles:
                if not isinstance(v, dict):
                    continue
                brand = BRAND_ALIASES.get(v.get("brand", ""), v.get("brand", ""))
                username = v.get("username", "")
                if brand not in BRAND_CONFIG or not username:
                    continue
                days_left = _check_token_expiry(brand, username)
                if days_left is not None:
                    update_ha_sensor(brand, username, days_remaining=days_left)
        except Exception as e:
            print(f"[SENSOR] Refresh error: {e}", file=sys.stderr, flush=True)
        time.sleep(INTERVAL)

threading.Thread(target=_sensor_refresh_loop, daemon=True).start()


# Periodic auto-renewal check (every 24 hours)
def _auto_renewal_loop():
    """Check token expiry daily and renew if needed (<14 days remaining)."""
    import sys
    INTERVAL = int(os.environ.get("RENEWAL_INTERVAL", 24 * 60 * 60))  # default: 24h
    # Wait before first check (auto-start already runs on boot)
    time.sleep(INTERVAL)
    while True:
        try:
            vehicles = _get_vehicles_config()
            if not vehicles:
                time.sleep(INTERVAL)
                continue
            needs_renewal = False
            for v in vehicles:
                if not isinstance(v, dict):
                    continue
                brand = BRAND_ALIASES.get(v.get("brand", ""), v.get("brand", ""))
                username = v.get("username", "")
                if brand not in BRAND_CONFIG or not username:
                    continue
                days_left = _check_token_expiry(brand, username)
                if days_left is not None and days_left <= 14:
                    needs_renewal = True
                    break
            if needs_renewal:
                print("[RENEWAL] Token expiring soon, triggering auto-renewal...", file=sys.stderr, flush=True)
                _auto_start_login(force=False)
        except Exception as e:
            print(f"[RENEWAL] Error: {e}", file=sys.stderr, flush=True)
        time.sleep(INTERVAL)

threading.Thread(target=_auto_renewal_loop, daemon=True).start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9876)

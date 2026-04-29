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
                 text-transform: uppercase; letter-spacing: 0.8px; }
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


def update_ha_sensor(brand, username=""):
    """Create/update a Home Assistant sensor with the token expiry date (per vehicle)."""
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        return
    try:
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=TOKEN_EXPIRY_DAYS)
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
                "generated": now.strftime("%Y-%m-%d %H:%M"),
                "expires": expiry.strftime("%Y-%m-%d %H:%M"),
                "days_remaining": TOKEN_EXPIRY_DAYS,
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
    resultDiv.innerHTML = msg + '<div style="margin-top:12px;color:var(--text-secondary);font-size:13px;" id="evcc-countdown">Resetting in 30s...</div><button class="btn btn-secondary" style="margin-top:8px;" onclick="evccReset()">Reset now</button>';
    var seconds = 30;
    var timer = setInterval(function() {{
        seconds--;
        var el = document.getElementById('evcc-countdown');
        if (el) el.textContent = 'Resetting in ' + seconds + 's...';
        if (seconds <= 0) {{ clearInterval(timer); evccReset(); }}
    }}, 1000);
}}
function evccReset() {{
    fetch(bp('/reset'), {{ method: 'POST' }}).then(function() {{ location.href = bp('/'); }});
}}
{"// Auto-connect if evcc is configured\nwindow.addEventListener('load', function() { document.getElementById('evcc-result').innerHTML = '<div class=\"notice notice-info\">Connecting to evcc...</div>'; evccLoadVehicles(); });" if evcc_configured else ""}
</script>""")

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
    return flask_redirect("/")

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
        result = _headless_login_eu(username, password, config)
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
    # Determine brand from config for sensor/timestamp
    _brand = next((k for k, v in BRAND_CONFIG.items() if v.get("client_id") == config.get("client_id")), "eu_kia")
    update_ha_sensor(_brand, username)
    _save_token_timestamp(_brand, username)

    return {"ok": True, "message": "Login successful — tokens generated!"}

@app.route("/api/status")
def api_status():
    return jsonify({"status": state["status"], "log": format_log()})


# ── Token API ───────────────────────────────────────────────

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
    return jsonify({"vehicles": result})


@app.route("/api/tokens", methods=["POST"])
def api_tokens_generate():
    """Generate tokens for all configured vehicles (or force renew).
    
    Request body (optional):
      { "force": true }   — renew even if token is still valid
    
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
    data = request.get_json(silent=True) or {}
    force = data.get("force", False)
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
            result = _headless_login_eu(username, password, config)
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
    if not evcc_url:
        return jsonify({"ok": False, "error": "No evcc URL provided"})
    try:
        session = req_lib.Session()
        session.verify = False
        # Check if auth is required
        auth_resp = session.get(f"{evcc_url}/api/auth/status", timeout=10)
        needs_auth = auth_resp.status_code == 200 and auth_resp.text.strip() == "false"
        if needs_auth:
            if not password:
                return jsonify({"ok": False, "error": "evcc requires admin password"})
            resp = session.post(f"{evcc_url}/api/auth/login",
                                json={"password": password}, timeout=10)
            if resp.status_code == 401:
                return jsonify({"ok": False, "error": "Invalid admin password"})
            if resp.status_code != 200:
                return jsonify({"ok": False, "error": f"Login failed ({resp.status_code})"})
        # Get vehicles
        resp = session.get(f"{evcc_url}/api/config/devices/vehicle", timeout=10)
        if resp.status_code == 401:
            return jsonify({"ok": False, "error": "Authentication required — please enter your evcc admin password"})
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": f"Could not fetch vehicles ({resp.status_code})"})
        vehicles = resp.json()
        # Filter for Hyundai/Kia templates
        result = []
        for v in vehicles:
            cfg = v.get("config", {})
            tmpl = cfg.get("template", "")
            if tmpl in ("hyundai", "kia"):
                result.append({
                    "id": v.get("id"),
                    "name": v.get("name", ""),
                    "title": cfg.get("title", v.get("name", "")),
                    "template": tmpl,
                })
        return jsonify({"ok": True, "vehicles": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/evcc/update", methods=["POST"])
def evcc_update():
    """Update a vehicle's password (refresh token) in evcc."""
    data = request.get_json()
    evcc_url = data.get("url", "").rstrip("/")
    password = data.get("password", "")
    vehicle_id = data.get("vehicle_id")
    token = state.get("refresh_token")
    if not all([evcc_url, vehicle_id, token]):
        return jsonify({"ok": False, "error": "Missing parameters"})
    try:
        session = req_lib.Session()
        session.verify = False
        # Check if auth is required and login
        auth_resp = session.get(f"{evcc_url}/api/auth/status", timeout=10)
        needs_auth = auth_resp.status_code == 200 and auth_resp.text.strip() == "false"
        if needs_auth:
            resp = session.post(f"{evcc_url}/api/auth/login",
                                json={"password": password}, timeout=10)
            if resp.status_code != 200:
                return jsonify({"ok": False, "error": f"Login failed ({resp.status_code})"})
        # Get current vehicle config
        resp = session.get(f"{evcc_url}/api/config/devices/vehicle/{vehicle_id}", timeout=10)
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": f"Could not fetch vehicle ({resp.status_code})"})
        vehicle = resp.json()
        cfg = vehicle.get("config", {})
        # Update password with refresh token
        cfg["password"] = token
        payload = {"type": vehicle.get("type", "template")}
        payload.update(cfg)
        # Test first
        resp = session.post(f"{evcc_url}/api/config/test/vehicle/merge/{vehicle_id}",
                            json=payload, timeout=30)
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": f"Token test failed ({resp.status_code}): {resp.text[:200]}"})
        # Apply update
        resp = session.put(f"{evcc_url}/api/config/devices/vehicle/{vehicle_id}",
                           json=payload, timeout=15)
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": f"Update failed ({resp.status_code}): {resp.text[:200]}"})
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/evcc/restart", methods=["POST"])
def evcc_restart():
    """Restart evcc — via HA Supervisor API if available, otherwise via evcc shutdown."""
    data = request.get_json()
    evcc_url = data.get("url", "").rstrip("/")
    password = data.get("password", "")
    if not evcc_url:
        return jsonify({"ok": False, "error": "No evcc URL provided"})

    # Try HA Supervisor API first (if running as HA addon)
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if supervisor_token:
        try:
            headers = {"Authorization": f"Bearer {supervisor_token}"}
            # List all addons to find evcc
            resp = req_lib.get("http://supervisor/addons", headers=headers, timeout=10)
            if resp.status_code == 200:
                addons = resp.json().get("data", {}).get("addons", [])
                evcc_slug = None
                for addon in addons:
                    name = (addon.get("name", "") or "").lower()
                    slug = (addon.get("slug", "") or "").lower()
                    if "evcc" in name or "evcc" in slug:
                        evcc_slug = addon.get("slug")
                        break
                if evcc_slug:
                    resp = req_lib.post(f"http://supervisor/addons/{evcc_slug}/restart",
                                        headers=headers, timeout=60)
                    if resp.status_code == 200:
                        return jsonify({"ok": True})
                    return jsonify({"ok": False, "error": f"Supervisor restart failed ({resp.status_code})"})
        except Exception:
            pass  # Fall through to evcc shutdown

    # Fallback: evcc shutdown endpoint (for Docker/native installs)
    try:
        session = req_lib.Session()
        session.verify = False
        auth_resp = session.get(f"{evcc_url}/api/auth/status", timeout=10)
        needs_auth = auth_resp.status_code == 200 and auth_resp.text.strip() == "false"
        if needs_auth and password:
            session.post(f"{evcc_url}/api/auth/login",
                         json={"password": password}, timeout=10)
        resp = session.post(f"{evcc_url}/api/system/shutdown", timeout=10)
        if resp.status_code in (200, 204):
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": f"Restart failed ({resp.status_code})"})
    except req_lib.exceptions.ConnectionError:
        # Connection error is expected — evcc is shutting down
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

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
                continue
            elif days_left is not None:
                log(f"Vehicle {i+1}: {config['brand_name']} — token expires in {days_left} days, renewing...")

        log(f"Vehicle {i+1}: {config['brand_name']} — logging in...")

        try:
            result = _headless_login_eu(username, password, config)
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
        # Auto-transfer to evcc
        evcc_url = os.environ.get("EVCC_URL", "").rstrip("/")
        evcc_password = os.environ.get("EVCC_PASSWORD", "")
        if evcc_url:
            _auto_evcc_transfer(evcc_url, evcc_password)
    elif state["vehicles"]:
        state["status"] = "success"  # partial success
        log("Auto-start: some vehicles failed, check log.", "warn")
    else:
        state["status"] = "idle"
        log("Auto-start: no vehicles processed.", "warn")


def _auto_evcc_transfer(evcc_url, evcc_password):
    """Auto-transfer refresh token to evcc after successful login."""
    try:
        log(f"Auto-start: connecting to evcc ({evcc_url})...")
        session = req_lib.Session()
        session.verify = False
        session.verify = False  # Allow self-signed certs
        # Login if needed
        auth_resp = session.get(f"{evcc_url}/api/auth/status", timeout=10)
        if auth_resp.status_code == 200 and auth_resp.text.strip() == "false":
            if evcc_password:
                session.post(f"{evcc_url}/api/auth/login",
                             json={"password": evcc_password}, timeout=10)
        # Get vehicles
        resp = session.get(f"{evcc_url}/api/config/devices/vehicle", timeout=10)
        if resp.status_code != 200:
            log(f"Auto-start: could not fetch evcc vehicles ({resp.status_code})", "warn")
            return
        data = resp.json()
        all_vehicles = data.get("result", data) if isinstance(data, dict) else data
        if not isinstance(all_vehicles, list):
            all_vehicles = []
        vehicles = [v for v in all_vehicles
                    if isinstance(v, dict) and any(t in str(v.get("config", v)).lower()
                           for t in ("hyundai", "kia", "bluelink"))]
        if not vehicles:
            log("Auto-start: no Hyundai/Kia vehicles found in evcc", "warn")
            return
        log(f"Auto-start: found {len(vehicles)} vehicle(s) in evcc", "ok")
        # Build a map of brand → token from generated vehicles
        token_map = {}
        for sv in state.get("vehicles", []):
            if sv.get("status") == "ok" and sv.get("refresh_token"):
                # Map both "kia" and "hyundai" to match evcc template names
                brand_name = sv.get("brand_name", "").lower()
                token_map[brand_name] = sv["refresh_token"]
        if not token_map:
            # Fallback: use the last generated token for all
            token_map["kia"] = state.get("refresh_token", "")
            token_map["hyundai"] = state.get("refresh_token", "")
        log(f"Auto-start: tokens available for: {', '.join(token_map.keys())}")

        for v in vehicles:
            vid = v["id"]
            title = v.get("config", {}).get("title", f"Vehicle {vid}")
            try:
                # Get current config
                cfg_resp = session.get(f"{evcc_url}/api/config/devices/vehicle/{vid}", timeout=10)
                if cfg_resp.status_code != 200:
                    log(f"Auto-start: could not fetch config for {title}", "warn")
                    continue
                vehicle_data = cfg_resp.json()
                cfg = vehicle_data.get("config", {})
                # Find the right token for this vehicle's brand
                tmpl = cfg.get("template", "").lower()
                token = token_map.get(tmpl, token_map.get("kia", token_map.get("hyundai", "")))
                if not token:
                    log(f"Auto-start: no token available for {title} (template: {tmpl})", "warn")
                    continue
                cfg["password"] = token
                payload = {"type": vehicle_data.get("type", "template")}
                payload.update(cfg)
                # Test + apply
                session.post(f"{evcc_url}/api/config/test/vehicle/merge/{vid}",
                             json=payload, timeout=30)
                resp = session.put(f"{evcc_url}/api/config/devices/vehicle/{vid}",
                                   json=payload, timeout=15)
                if resp.status_code == 200:
                    log(f"Auto-start: token sent to {title}", "ok")
                else:
                    log(f"Auto-start: failed to update {title} ({resp.status_code}): {resp.text[:200]}", "warn")
            except Exception as e:
                log(f"Auto-start: error updating {title}: {e}", "warn")
        # Restart evcc
        log("Auto-start: restarting evcc...")
        supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
        if supervisor_token:
            try:
                resp = req_lib.post("http://supervisor/addons/a0d7b954_evcc/restart",
                                    headers={"Authorization": f"Bearer {supervisor_token}"},
                                    timeout=30)
                if resp.status_code == 200:
                    log("Auto-start: evcc restarted via HA Supervisor", "ok")
                    return
            except Exception:
                pass
        try:
            session.post(f"{evcc_url}/api/system/shutdown", timeout=10)
            log("Auto-start: evcc restart triggered", "ok")
        except Exception:
            log("Auto-start: could not restart evcc automatically", "warn")
    except Exception as e:
        log(f"Auto-start: evcc transfer error: {e}", "warn")

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9876)

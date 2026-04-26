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
    "status": "idle", "refresh_token": None, "access_token": None,
    "error": None, "test_result": "", "log": [], "brand_override": None,
}

_MOBILE_UA = "Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus Build/JRO03C) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19_CCS_APP_AOS"

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
    return f"""<!DOCTYPE html>
<html lang="de"><head>
<title>Bluelink Token Generator</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<style>{STYLE}</style></head><body>
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

def update_ha_sensor(brand):
    """Create/update a Home Assistant sensor with the token expiry date."""
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        return  # Not running as HA addon
    try:
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=TOKEN_EXPIRY_DAYS)
        headers = {
            "Authorization": f"Bearer {supervisor_token}",
            "Content-Type": "application/json",
        }
        sensor_data = {
            "state": expiry.strftime("%Y-%m-%d"),
            "attributes": {
                "friendly_name": f"Bluelink Token Expiry ({brand.title()})",
                "device_class": "date",
                "icon": "mdi:key-clock",
                "generated": now.strftime("%Y-%m-%d %H:%M"),
                "expires": expiry.strftime("%Y-%m-%d %H:%M"),
                "days_remaining": TOKEN_EXPIRY_DAYS,
                "brand": brand,
            },
        }
        resp = req_lib.post(
            f"http://supervisor/core/api/states/sensor.bluelink_token_expiry",
            headers=headers, json=sensor_data, timeout=10)
        if resp.status_code in (200, 201):
            log("Home Assistant sensor updated (sensor.bluelink_token_expiry).", "ok")
        else:
            log(f"Could not update HA sensor ({resp.status_code}).", "warn")
    except Exception as e:
        log(f"Could not update HA sensor: {e}", "warn")

# ── Routes ──────────────────────────────────────────────────

@app.route("/")
def index():
    brand = get_brand()
    config = BRAND_CONFIG[brand]
    bt = f"{config['region_name']} {config['brand_name']}"
    s = state["status"]

    if s == "idle":
        env_user = os.environ.get("BLUELINK_USERNAME", "")
        env_pass = os.environ.get("BLUELINK_PASSWORD", "")
        default_brand = os.environ.get("BRAND", "auto").lower()
        default_brand = BRAND_ALIASES.get(default_brand, default_brand)
        brand_fixed = default_brand in BRAND_CONFIG
        is_eu = brand in ("eu_kia", "eu_hyundai")

        if brand_fixed:
            brand_html = f'<input type="hidden" name="brand" value="{default_brand}">'
        else:
            show_all = True
            regions = {}
            for key, cfg in BRAND_CONFIG.items():
                rn = cfg["region_name"]
                regions.setdefault(rn, []).append((key, cfg["brand_name"]))
            options_html = ""
            for region, entries in regions.items():
                options_html += f'<optgroup label="{region}">'
                for key, bname in entries:
                    sel = "selected" if key == brand else ""
                    options_html += f'<option value="{key}" {sel}>{bname}</option>'
                options_html += "</optgroup>"
            brand_html = f"""
        <div style="margin-bottom: 16px;">
            <label for="brand-select" class="section-label">Region &amp; Brand</label>
            <select id="brand-select" name="brand" style="
                padding: 10px 14px; border: 1px solid var(--border); border-radius: 10px;
                font-size: 14px; font-family: inherit; background: var(--surface);
                cursor: pointer; min-width: 200px;">
                {options_html}
            </select>
        </div>"""

        if is_eu:
            # EU brands: simple credentials form, headless login
            return render(f"""
<div class="card">
    <div class="card-title">Generate Refresh Token</div>
    <p style="margin-bottom: 16px; color: var(--text-secondary); font-size: 14px;">
        Enter your {bt} Bluelink credentials (same as the mobile app).
        The token will be generated automatically — no browser needed.
    </p>
    <form method="POST" action="/api/quicklogin" id="login-form">
        {brand_html}
        <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:16px;">
            <input type="text" name="username" id="ql-user" placeholder="E-Mail / Username"
                   value="{html_lib.escape(env_user)}" required>
            <input type="password" name="password" id="ql-pass" placeholder="Password"
                   value="{html_lib.escape(env_pass)}" required>
        </div>
        <button type="submit" class="btn btn-primary" id="ql-btn">Generate Token</button>
    </form>
    <div id="ql-result" style="margin-top:12px;">{'<div class="notice notice-error">' + html_lib.escape(state.get("error", "")) + '</div>' if state.get("error") else ''}</div>
    <div id="ql-log" style="margin-top:12px;">{('<details open><summary>Log</summary><div class="log">' + format_log() + '</div></details>') if state.get('log') else ''}</div>
</div>
<script>
document.getElementById('login-form').addEventListener('submit', function(e) {{
    e.preventDefault();
    var btn = document.getElementById('ql-btn');
    var res = document.getElementById('ql-result');
    btn.disabled = true; btn.textContent = 'Generating...';
    res.innerHTML = '<div class="notice notice-info">Logging in and generating token...</div>';
    fetch('/api/quicklogin', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
            username: document.getElementById('ql-user').value,
            password: document.getElementById('ql-pass').value,
            brand: (document.getElementById('brand-select') || {{}}).value || '{brand}'
        }})
    }}).then(function(r){{ return r.json(); }}).then(function(d) {{
        if (d.ok) {{
            location.reload();
        }} else {{
            location.reload();
        }}
    }}).catch(function() {{
        location.reload();
    }});
}});
</script>""")
        else:
            # Non-EU or no curl_cffi: browser-based flow
            creds_note = ("Credentials are configured and will be filled in automatically.") if (env_user and env_pass) else (
                "You will need to enter your credentials in the browser.")
            return render(f"""
<div class="card">
    <div class="card-title">Generate Refresh Token</div>
    <p style="margin-bottom: 12px; color: var(--text-secondary); font-size: 14px;">
        A browser will open in the background. Complete the Bluelink login
        through the embedded viewer to generate the token.
    </p>
    <div class="notice notice-info">{creds_note}</div>
    <form method="POST" action="/start">
        {brand_html}
        <button type="submit" class="btn btn-primary">Start token generation</button>
    </form>
</div>""")

    elif s == "processing":
        return render(f"""
<div class="card">
    <div class="card-title">Processing</div>
    <div class="notice notice-info">Generating token...</div>
    <div class="log" id="log-box">{format_log()}</div>
</div>
<script>
(function poll() {{
    fetch('/api/status').then(function(r){{ return r.json(); }}).then(function(d) {{
        document.getElementById('log-box').innerHTML = d.log;
        if (d.status !== 'processing') location.reload();
        else setTimeout(poll, 2000);
    }}).catch(function(){{ setTimeout(poll, 2000); }});
}})();
</script>""")

    elif s == "success":
        rt = html_lib.escape(state.get("refresh_token", ""))
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
    <div class="notice notice-success">The refresh token was generated successfully.</div>
    {test_html}
    <div style="margin: 20px 0;">
        <div class="token-label">Refresh Token</div>
        <div class="token-box" id="refresh">{rt}</div>
        <button class="copy-link" data-copy="refresh" onclick="copyToken('refresh')">Copy to clipboard</button>
    </div>
    <div class="notice notice-warning">
        This token is valid for 180 days (expires {(datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS)).strftime('%B %d, %Y')}). After that you will need to generate a new one.
    </div>
    <hr class="divider">
    <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 16px;">
        Use this refresh token as the password together with your regular username
        when configuring the evcc or Home Assistant integration.
    </p>
    <div class="actions">
        <form method="POST" action="/test" style="margin:0;">
            <button type="submit" class="btn btn-secondary">Verify token</button>
        </form>
        <form method="POST" action="/reset" style="margin:0;">
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
    fetch('/api/evcc/vehicles', {{
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
        fetch('/api/evcc/update', {{
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
    fetch('/api/evcc/restart', {{
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
    fetch('/reset', {{ method: 'POST' }}).then(function() {{ location.href = '/'; }});
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
    <form method="POST" action="/reset">
        <button type="submit" class="btn btn-danger">Reset</button>
    </form>
</div>""")

    return render('<div class="card">Unknown state</div>')

@app.route("/reset", methods=["POST"])
def reset():
    state.update({"status": "idle", "refresh_token": None, "access_token": None,
                  "error": None, "test_result": "", "log": [], "brand_override": None})
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
    """Direct headless login for EU brands — no browser, no Start button needed."""
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")
    chosen_brand = data.get("brand", "").lower()
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"})

    # Use brand from request, fall back to get_brand()
    chosen_brand = BRAND_ALIASES.get(chosen_brand, chosen_brand)
    if chosen_brand in BRAND_CONFIG:
        state["brand_override"] = chosen_brand
    brand = chosen_brand if chosen_brand in BRAND_CONFIG else get_brand()
    config = BRAND_CONFIG[brand]
    if brand not in ("eu_kia", "eu_hyundai"):
        return jsonify({"ok": False, "error": "Quick login only supported for EU brands"})

    state["status"] = "processing"
    state["log"] = []
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
    update_ha_sensor(get_brand())

    return {"ok": True, "message": "Login successful — tokens generated!"}

@app.route("/api/status")
def api_status():
    return jsonify({"status": state["status"], "log": format_log()})

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

def _auto_start_login():
    """Auto-start headless login if credentials are configured via env vars."""
    username = os.environ.get("BLUELINK_USERNAME", "")
    password = os.environ.get("BLUELINK_PASSWORD", "")
    brand_env = os.environ.get("BRAND", "auto").lower()
    brand_env = BRAND_ALIASES.get(brand_env, brand_env)

    if not username or not password:
        return
    if brand_env not in ("eu_kia", "eu_hyundai") and brand_env != "auto":
        return

    brand = brand_env if brand_env in BRAND_CONFIG else "eu_kia"
    config = BRAND_CONFIG[brand]

    print(f"[AUTO] Credentials configured — starting headless login for {brand}...")
    state["status"] = "processing"
    state["log"] = []
    log("Auto-start: credentials found, trying headless login...")

    try:
        result = _headless_login_eu(username, password, config)
        if result.get("ok"):
            log("Auto-start: login successful!", "ok")
            # Auto-transfer to evcc if configured
            evcc_url = os.environ.get("EVCC_URL", "").rstrip("/")
            evcc_password = os.environ.get("EVCC_PASSWORD", "")
            if evcc_url and state.get("refresh_token"):
                _auto_evcc_transfer(evcc_url, evcc_password)
        else:
            log(f"Auto-start: failed: {result.get('error', 'unknown')}", "warn")
            log("Open the web UI to try again.", "warn")
            state["status"] = "idle"
    except Exception as e:
        log(f"Auto-start: error: {e}", "warn")
        state["status"] = "idle"


def _auto_evcc_transfer(evcc_url, evcc_password):
    """Auto-transfer refresh token to evcc after successful login."""
    try:
        log(f"Auto-start: connecting to evcc ({evcc_url})...")
        session = req_lib.Session()
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
        vehicles = [v for v in resp.json().get("result", [])
                    if any(t in v.get("config", {}).get("type", "").lower()
                           for t in ("hyundai", "kia", "bluelink"))]
        if not vehicles:
            log("Auto-start: no Hyundai/Kia vehicles found in evcc", "warn")
            return
        log(f"Auto-start: found {len(vehicles)} vehicle(s) in evcc", "ok")
        token = state["refresh_token"]
        for v in vehicles:
            vid = v["id"]
            title = v.get("config", {}).get("title", f"Vehicle {vid}")
            try:
                # Get current config
                cfg_resp = session.get(f"{evcc_url}/api/config/devices/vehicle/{vid}", timeout=10)
                if cfg_resp.status_code != 200:
                    log(f"Auto-start: could not fetch config for {title}", "warn")
                    continue
                payload = {"type": "template"}
                payload.update(cfg_resp.json().get("result", {}).get("config", {}))
                payload["password"] = token
                # Test + apply
                session.post(f"{evcc_url}/api/config/test/vehicle/merge/{vid}",
                             json=payload, timeout=30)
                resp = session.put(f"{evcc_url}/api/config/devices/vehicle/{vid}",
                                   json=payload, timeout=15)
                if resp.status_code == 200:
                    log(f"Auto-start: token sent to {title}", "ok")
                else:
                    log(f"Auto-start: failed to update {title} ({resp.status_code})", "warn")
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

# Auto-start on import (when gunicorn loads the app)
threading.Thread(target=_auto_start_login, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9876)

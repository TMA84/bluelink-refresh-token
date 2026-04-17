#!/usr/bin/env python3
"""Bluelink Token Generator - Web Application with Selenium + noVNC"""

import os, re, time, threading, subprocess
import requests as req_lib
from flask import Flask, request, jsonify, redirect as flask_redirect
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import html as html_lib

app = Flask(__name__)

state = {
    "status": "idle", "refresh_token": None, "access_token": None,
    "error": None, "test_result": "", "log": [], "brand_override": None,
}

BRAND_CONFIG = {
    "kia": {
        "client_id": "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a",
        "client_secret": "secret",
        "base_url": "https://idpconnect-eu.kia.com/auth/api/v2/user/oauth2",
        "redirect_url_final": "https://prd.eu-ccapi.kia.com:8080/api/v1/user/oauth2/redirect",
        "login_url": "https://idpconnect-eu.kia.com/auth/api/v2/user/oauth2/authorize?ui_locales=de&scope=openid%20profile%20email%20phone&response_type=code&client_id=peukiaidm-online-sales&redirect_uri=https%3A%2F%2Fwww.kia.com%2Fapi%2Fbin%2Foneid%2Flogin&state=aHR0cHM6Ly93d3cua2lhLmNvbTo0NDMvZGUvP21zb2NraWQ9MjM1NDU0ODBmNmUyNjg5NDIwMmU0MDBjZjc2OTY5NWQmX3RtPTE3NTYzMTg3MjY1OTImX3RtPTE3NTYzMjQyMTcxMjY%3D_default",
        "success_selector": "a[class='logout user']",
        "code_pattern": r'^https://.*:8080/api/v1/user/oauth2/redirect',
    },
    "hyundai": {
        "client_id": "6d477c38-3ca4-4cf3-9557-2a1929a94654",
        "client_secret": "KUy49XxPzLpLuoK0xhBC77W6VXhmtQR9iQhmIFjjoY4IpxsV",
        "base_url": "https://idpconnect-eu.hyundai.com/auth/api/v2/user/oauth2",
        "redirect_url_final": "https://prd.eu-ccapi.hyundai.com:8080/api/v1/user/oauth2/token",
        "login_url": "https://idpconnect-eu.hyundai.com/auth/api/v2/user/oauth2/authorize?client_id=peuhyundaiidm-ctb&redirect_uri=https%3A%2F%2Fctbapi.hyundai-europe.com%2Fapi%2Fauth&nonce=&state=NL_&scope=openid+profile+email+phone&response_type=code&connector_client_id=peuhyundaiidm-ctb&connector_scope=&connector_session_key=&country=&captcha=1&ui_locales=en-US",
        "success_selector": "button.mail_check",
        "code_pattern": r'^https://.*:8080/api/v1/user/oauth2/token',
    },
}

STYLE = """
:root {
  --primary: #2563eb; --primary-hover: #1d4ed8; --primary-light: #dbeafe;
  --accent: #7c3aed; --accent-light: #ede9fe;
  --success: #059669; --success-bg: #d1fae5; --error: #dc2626; --error-bg: #fee2e2;
  --warning: #d97706; --warning-bg: #fef3c7; --info: #2563eb; --info-bg: #dbeafe;
  --text: #1e293b; --text-secondary: #64748b;
  --border: #e2e8f0; --surface: #ffffff; --bg: #f1f5f9;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: var(--bg); color: var(--text); min-height: 100vh; }
.header { background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #7c3aed 100%);
          padding: 20px 24px; margin-bottom: 24px; }
.header-inner { max-width: 1100px; margin: 0 auto; display: flex; align-items: center; gap: 14px; }
.header h1 { font-size: 20px; font-weight: 600; color: white; }
.header .brand { font-size: 11px; font-weight: 600; color: white;
                 background: rgba(255,255,255,0.2); padding: 3px 12px; border-radius: 20px;
                 text-transform: uppercase; letter-spacing: 0.8px; backdrop-filter: blur(4px); }
.container { max-width: 1100px; margin: 0 auto; padding: 0 24px 40px; }
.card { background: var(--surface); border-radius: 12px; padding: 24px;
        margin-bottom: 16px; border: 1px solid var(--border); box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.card-title { font-size: 17px; font-weight: 600; margin-bottom: 16px; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 10px 24px;
       border-radius: 8px; border: none; font-size: 14px; font-weight: 500;
       cursor: pointer; text-decoration: none; transition: all 0.2s; font-family: inherit; }
.btn-primary { background: var(--primary); color: white; }
.btn-primary:hover { background: var(--primary-hover); box-shadow: 0 2px 8px rgba(37,99,235,0.3); }
.btn-secondary { background: var(--surface); color: var(--primary); border: 1px solid var(--primary); }
.btn-secondary:hover { background: var(--primary-light); }
.btn-danger { background: var(--surface); color: var(--error); border: 1px solid var(--error); }
.btn-danger:hover { background: var(--error-bg); }
.token-label { font-size: 11px; font-weight: 600; color: var(--accent);
               text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.token-box { background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
             border: 1px solid var(--border); padding: 16px 18px; border-radius: 8px;
             word-break: break-all; font-family: 'JetBrains Mono', 'Roboto Mono', monospace;
             font-size: 13px; line-height: 1.7; border-left: 3px solid var(--accent); }
.copy-link { color: var(--primary); cursor: pointer; font-size: 13px; border: none;
             background: none; font-family: inherit; margin-top: 8px; display: inline-block; font-weight: 500; }
.copy-link:hover { text-decoration: underline; }
.notice { padding: 14px 18px; border-radius: 8px; margin-bottom: 16px;
          font-size: 14px; line-height: 1.5; border-left: 4px solid transparent; }
.notice-success { background: var(--success-bg); color: var(--success); border-left-color: var(--success); }
.notice-error { background: var(--error-bg); color: var(--error); border-left-color: var(--error); }
.notice-warning { background: var(--warning-bg); color: var(--warning); border-left-color: var(--warning); }
.notice-info { background: var(--info-bg); color: var(--info); border-left-color: var(--info); }
.divider { border: none; border-top: 1px solid var(--border); margin: 20px 0; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
.log { background: #0f172a; color: #94a3b8; padding: 16px 18px; border-radius: 8px;
       font-family: 'JetBrains Mono', 'Roboto Mono', monospace; font-size: 12px;
       max-height: 200px; overflow-y: auto; margin: 12px 0; line-height: 1.8; }
.log .ok { color: #34d399; } .log .warn { color: #fbbf24; } .log .err { color: #f87171; }
.vnc-frame { width: 100%; height: 700px; border: 1px solid var(--border);
             border-radius: 8px; margin: 12px 0; background: #0f172a; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.paste-row { display: flex; gap: 8px; margin-bottom: 4px; }
.paste-row input { flex: 1; padding: 10px 14px; border: 1px solid var(--border);
                   border-radius: 8px; font-size: 14px; font-family: inherit;
                   -webkit-text-security: disc; transition: border-color 0.2s; }
.paste-row input:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
.paste-row button { white-space: nowrap; }
.hint { font-size: 12px; color: var(--text-secondary); margin-top: 6px; line-height: 1.5; }
.section-label { font-size: 13px; font-weight: 600; color: var(--text-secondary);
                 margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
p { line-height: 1.6; }
details summary { cursor: pointer; font-size: 13px; color: var(--text-secondary); font-weight: 500; }
details summary:hover { color: var(--primary); }
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
function sendClipboard() {
    var input = document.getElementById('paste-text');
    var text = input.value;
    if (!text) return;
    fetch('/api/type', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: text})
    }).then(function(r) { return r.json(); }).then(function(d) {
        if (d.ok) {
            input.value = '';
            input.placeholder = 'Sent successfully';
            setTimeout(function() { input.placeholder = 'Paste text here...'; }, 2000);
        }
    });
}
"""

def render(content):
    brand = get_brand()
    return f"""<!DOCTYPE html>
<html lang="de"><head>
<title>Bluelink Token Generator</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<style>{STYLE}</style></head><body>
<div class="header"><div class="header-inner">
<h1>Bluelink Token Generator</h1>
<span class="brand">{brand}</span>
</div></div>
<div class="container">{content}</div>
<script>{SCRIPT}</script></body></html>"""

def get_brand():
    override = state.get("brand_override")
    if override and override in BRAND_CONFIG:
        return override
    return os.environ.get("BRAND", "hyundai").lower()

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

def get_token_thread(brand):
    config = BRAND_CONFIG[brand]
    base_url = config["base_url"]
    token_url = f"{base_url}/token"
    redirect_url = (f"{base_url}/authorize?response_type=code&client_id={config['client_id']}"
                    f"&redirect_uri={config['redirect_url_final']}&lang=de&state=ccsp")
    driver = None
    try:
        state["status"] = "waiting_login"
        state["log"] = []
        log("Starting browser...")
        options = webdriver.ChromeOptions()
        options.binary_location = "/usr/bin/chromium-browser"
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,800")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus "
            "Build/JRO03C) AppleWebKit/535.19 (KHTML, like Gecko) "
            "Chrome/18.0.1025.166 Mobile Safari/535.19_CCS_APP_AOS")
        service = webdriver.ChromeService(executable_path="/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        log(f"Opening {brand.title()} login page...")
        driver.get(config["login_url"])

        # Auto-fill credentials if configured
        username = os.environ.get("BLUELINK_USERNAME", "")
        password = os.environ.get("BLUELINK_PASSWORD", "")
        if username and password:
            log("Auto-filling credentials...")
            try:
                email_selector = ("input[type='email'], input[type='text'][name*='mail'], "
                    "input[type='text'][name*='user'], input[name='username'], "
                    "input[id*='email'], input[id*='user'], input[type='text']")
                # Wait for the email field to appear instead of a fixed sleep
                email_field = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, email_selector)))
                email_field.clear()
                email_field.send_keys(username)
                log("Username entered.", "ok")

                # Wait for password field to appear
                pw_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
                pw_field.clear()
                pw_field.send_keys(password)
                log("Password entered.", "ok")
                log("Credentials filled — please verify and click Sign In in the browser.", "warn")
            except Exception as e:
                log(f"Could not auto-fill: {e} — please enter manually.", "warn")
        else:
            log("Waiting for login — please sign in using the browser below.", "warn")
        wait = WebDriverWait(driver, 300)
        if brand == "kia":
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, config["success_selector"])))
        else:
            wait.until(EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, config["success_selector"])),
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.ctb_button"))))
        log("Login successful.", "ok")
        state["status"] = "processing"
        log("Retrieving authorization code...")
        driver.get(redirect_url)
        time.sleep(3)
        current_url = ""
        for i in range(15):
            current_url = driver.current_url
            log(f"Waiting for redirect ({i+1}/15)...")
            if re.match(config["code_pattern"], current_url): break
            time.sleep(1)
        code_match = re.search(r'code=([0-9a-fA-F-]{36}\.[0-9a-fA-F-]{36}\.[0-9a-fA-F-]{36})', current_url)
        if not code_match:
            state["status"] = "error"
            state["error"] = f"No auth code found in URL: {current_url[:120]}"
            log(state["error"], "err")
            return
        log("Authorization code received.", "ok")
        log("Exchanging code for token...")
        data = {"grant_type": "authorization_code", "code": code_match.group(1),
                "redirect_uri": config["redirect_url_final"],
                "client_id": config["client_id"], "client_secret": config["client_secret"]}
        response = req_lib.post(token_url, data=data, timeout=15)
        if response.status_code == 200:
            tokens = response.json()
            state["refresh_token"] = tokens.get("refresh_token", "N/A")
            state["access_token"] = tokens.get("access_token", "N/A")
            state["status"] = "success"
            log("Token generated successfully.", "ok")
        else:
            state["status"] = "error"
            state["error"] = f"API error {response.status_code}: {response.text[:200]}"
            log(state["error"], "err")
    except TimeoutException:
        state["status"] = "error"
        state["error"] = "Timeout — login was not completed within 5 minutes."
        log(state["error"], "err")
    except Exception as e:
        state["status"] = "error"
        state["error"] = str(e)
        log(f"Error: {e}", "err")
    finally:
        if driver:
            try: driver.quit()
            except: pass
        log("Browser closed.")

# ── Routes ──────────────────────────────────────────────────

@app.route("/")
def index():
    brand = get_brand()
    bt = brand.title()
    s = state["status"]

    if s == "idle":
        has_creds = bool(os.environ.get("BLUELINK_USERNAME")) and bool(os.environ.get("BLUELINK_PASSWORD"))
        creds_note = ("Credentials are configured and will be filled in automatically. "
                      "You only need to click the Sign In button.") if has_creds else (
                      "No credentials configured. You will need to enter them manually in the browser. "
                      "Tip: Set username and password in the addon configuration for auto-fill.")
        default_brand = os.environ.get("BRAND", "hyundai").lower()
        kia_sel = "selected" if default_brand == "kia" else ""
        hyu_sel = "selected" if default_brand != "kia" else ""
        return render(f"""
<div class="card">
    <div class="card-title">Generate Refresh Token</div>
    <p style="margin-bottom: 12px; color: var(--text-secondary); font-size: 14px;">
        A Chromium browser will open in the background. You can interact with it
        through the embedded viewer below to complete the Bluelink login.
    </p>
    <div class="notice notice-info">{creds_note}</div>
    <form method="POST" action="/start">
        <div style="margin-bottom: 16px;">
            <label for="brand-select" class="section-label">Brand</label>
            <select id="brand-select" name="brand" style="
                padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px;
                font-size: 14px; font-family: inherit; background: var(--surface);
                cursor: pointer; min-width: 200px; transition: border-color 0.2s;">
                <option value="hyundai" {hyu_sel}>Hyundai</option>
                <option value="kia" {kia_sel}>Kia</option>
            </select>
        </div>
        <button type="submit" class="btn btn-primary">Start token generation</button>
    </form>
</div>""")

    elif s == "waiting_login":
        return render(f"""
<div class="card">
    <div class="card-title">Sign in to {bt} Bluelink</div>
    <div class="notice notice-warning">
        Waiting for login. Use your {bt} Bluelink credentials (same as the mobile app).
        The session will time out after 5 minutes.
    </div>
    <div class="log" id="log-box">{format_log()}</div>
    <hr class="divider">
    <div class="section-label">Paste text into browser</div>
    <div class="paste-row">
        <input type="password" id="paste-text" placeholder="Paste text here (e.g. password)..."
               onkeydown="if(event.key==='Enter')sendClipboard()">
        <button class="btn btn-secondary" onclick="sendClipboard()">Send</button>
    </div>
    <p class="hint">Click into the input field in the browser below first, then paste your text above and press Send.</p>
    <hr class="divider">
    <div class="section-label">Remote browser</div>
    <iframe src="/novnc" class="vnc-frame" id="vnc"></iframe>
</div>
<script>
(function poll() {{
    fetch('/api/status').then(function(r){{ return r.json(); }}).then(function(d) {{
        document.getElementById('log-box').innerHTML = d.log;
        if (d.status !== 'waiting_login') location.reload();
        else setTimeout(poll, 3000);
    }}).catch(function(){{ setTimeout(poll, 3000); }});
}})();
</script>""")

    elif s == "processing":
        return render(f"""
<div class="card">
    <div class="card-title">Processing</div>
    <div class="notice notice-info">Login successful. Retrieving token...</div>
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
        This token is valid for 180 days. After that you will need to generate a new one.
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
            <button type="submit" class="btn btn-danger">Generate new token</button>
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
    <button class="btn btn-secondary" onclick="evccLoadVehicles()" id="evcc-connect-btn">Connect</button>
    <div id="evcc-vehicles" style="display:none; margin-top: 16px;">
        <div class="section-label">Vehicle</div>
        <select id="evcc-vehicle-select" style="
            width: 100%; padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px;
            font-size: 14px; font-family: inherit; background: var(--surface); margin-bottom: 12px;">
        </select>
        <button class="btn btn-primary" onclick="evccSendToken()">Send token to evcc</button>
    </div>
    <div id="evcc-result" style="margin-top: 12px;"></div>
</div>
<script>
function evccLoadVehicles() {{
    var url = document.getElementById('evcc-url').value;
    var pw = document.getElementById('evcc-password').value;
    var btn = document.getElementById('evcc-connect-btn');
    var resultDiv = document.getElementById('evcc-result');
    btn.textContent = 'Connecting...'; btn.disabled = true; resultDiv.innerHTML = '';
    fetch('/api/evcc/vehicles', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{url: url, password: pw}})
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
        btn.textContent = 'Connect'; btn.disabled = false;
        if (!d.ok) {{ resultDiv.innerHTML = '<div class="notice notice-error">' + d.error + '</div>'; return; }}
        if (d.vehicles.length === 0) {{ resultDiv.innerHTML = '<div class="notice notice-warning">No Hyundai/Kia vehicles found in evcc.</div>'; return; }}
        var select = document.getElementById('evcc-vehicle-select');
        select.innerHTML = '';
        d.vehicles.forEach(function(v) {{
            var opt = document.createElement('option');
            opt.value = v.id;
            opt.textContent = v.title + ' (' + v.template + ')';
            select.appendChild(opt);
        }});
        if (d.vehicles.length === 1) {{
            // Single vehicle — auto-send token
            resultDiv.innerHTML = '<div class="notice notice-info">Found ' + d.vehicles[0].title + ' — sending token...</div>';
            evccSendToken();
        }} else {{
            document.getElementById('evcc-vehicles').style.display = 'block';
            resultDiv.innerHTML = '<div class="notice notice-success">Connected — ' + d.vehicles.length + ' vehicles found. Select one below.</div>';
        }}
    }}).catch(function(e) {{ btn.textContent = 'Connect'; btn.disabled = false; resultDiv.innerHTML = '<div class="notice notice-error">Connection failed: ' + e + '</div>'; }});
}}
function evccSendToken() {{
    var url = document.getElementById('evcc-url').value;
    var pw = document.getElementById('evcc-password').value;
    var vid = document.getElementById('evcc-vehicle-select').value;
    var resultDiv = document.getElementById('evcc-result');
    resultDiv.innerHTML = '<div class="notice notice-info">Sending token...</div>';
    fetch('/api/evcc/update', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{url: url, password: pw, vehicle_id: parseInt(vid)}})
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
        if (d.ok) {{
            resultDiv.innerHTML = '<div class="notice notice-success">Token transferred — restarting evcc...</div>';
            evccRestart();
        }} else {{
            resultDiv.innerHTML = '<div class="notice notice-error">' + d.error + '</div>';
        }}
    }}).catch(function(e) {{ resultDiv.innerHTML = '<div class="notice notice-error">Transfer failed: ' + e + '</div>'; }});
}}
function evccRestart() {{
    var url = document.getElementById('evcc-url').value;
    var pw = document.getElementById('evcc-password').value;
    var resultDiv = document.getElementById('evcc-result');
    fetch('/api/evcc/restart', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{url: url, password: pw}})
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
        if (d.ok) {{ resultDiv.innerHTML = '<div class="notice notice-success">Token transferred and evcc restarted successfully!</div>'; }}
        else {{ resultDiv.innerHTML = '<div class="notice notice-success">Token transferred.</div><div class="notice notice-warning" style="margin-top:8px;">Could not restart evcc automatically: ' + d.error + '. Please restart evcc manually.</div>'; }}
    }}).catch(function(e) {{ resultDiv.innerHTML = '<div class="notice notice-success">Token transferred.</div><div class="notice notice-warning" style="margin-top:8px;">Could not restart evcc automatically. Please restart evcc manually.</div>'; }});
}}
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
        <button type="submit" class="btn btn-primary">Try again</button>
    </form>
</div>""")

    return render('<div class="card">Unknown state</div>')

@app.route("/start", methods=["POST"])
def start():
    chosen_brand = request.form.get("brand", "").lower()
    if chosen_brand in BRAND_CONFIG:
        state["brand_override"] = chosen_brand
    else:
        state["brand_override"] = None
    state.update({"status": "waiting_login", "refresh_token": None,
                  "access_token": None, "error": None, "test_result": "", "log": []})
    threading.Thread(target=get_token_thread, args=(get_brand(),), daemon=True).start()
    return render("""
<div class="card">
    <div class="notice notice-info">Starting browser... redirecting shortly.</div>
</div>
<script>setTimeout(function(){ location.href = '/'; }, 2000);</script>""")

@app.route("/reset", methods=["POST"])
def reset():
    state.update({"status": "idle", "refresh_token": None, "access_token": None,
                  "error": None, "test_result": "", "log": [], "brand_override": None})
    return flask_redirect("/")

@app.route("/novnc")
def novnc():
    host = request.host.split(":")[0]
    return (f'<!DOCTYPE html><html><head>'
            f'<meta http-equiv="refresh" content="0;url=http://{host}:6080/vnc.html?autoconnect=true&resize=scale">'
            f'</head><body></body></html>')

@app.route("/test", methods=["POST"])
def test_token():
    brand = get_brand()
    config = BRAND_CONFIG[brand]
    refresh_token = state.get("refresh_token")
    if not refresh_token:
        state["test_result"] = "No refresh token available."
        return flask_redirect("/")
    # The most reliable test: use the refresh token to get a new access token
    token_url = f"{config['base_url']}/token"
    try:
        data = {"grant_type": "refresh_token", "refresh_token": refresh_token,
                "client_id": config["client_id"], "client_secret": config["client_secret"]}
        response = req_lib.post(token_url, data=data, timeout=10)
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

@app.route("/api/type", methods=["POST"])
def api_type():
    data = request.get_json()
    text = data.get("text", "")
    if not text:
        return jsonify({"ok": False, "error": "No text"})
    try:
        subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "12", text],
                       env={**os.environ, "DISPLAY": ":99"}, timeout=10)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9876)

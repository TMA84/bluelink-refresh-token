#!/usr/bin/env python3
"""Bluelink Token Generator - Web Application with Selenium + noVNC"""

import os, re, time, threading, subprocess
from datetime import datetime, timedelta, timezone
import requests as req_lib
from flask import Flask, request, jsonify, redirect as flask_redirect
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import html as html_lib

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

_DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36_CCS_APP_AOS"
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
    # ── China ───────────────────────────────────────────────
    "cn_kia": {
        "client_id": "9d5df92a-06ae-435f-b459-8304f2efcc67",
        "client_secret": "tsXdkUg08Av2ZZzXOgWzJyxUT6yeSnNNQkXXPRdKWEANwl1p",
        "login_url": "https://prd.cn-ccapi.kia.com/api/v1/user/oauth2/authorize?response_type=code&client_id=9d5df92a-06ae-435f-b459-8304f2efcc67&redirect_uri=https://prd.cn-ccapi.kia.com:443/api/v1/user/oauth2/redirect",
        "token_url": "https://prd.cn-ccapi.kia.com/api/v1/user/oauth2/token",
        "redirect_url_final": "https://prd.cn-ccapi.kia.com:443/api/v1/user/oauth2/redirect",
        "success_selector": None,
        "user_agent": _DEFAULT_UA,
        "region_name": "China",
        "brand_name": "Kia",
    },
    "cn_hyundai": {
        "client_id": "72b3d019-5bc7-443d-a437-08f307cf06e2",
        "client_secret": "secret",
        "login_url": "https://prd.cn-ccapi.hyundai.com/api/v1/user/oauth2/authorize?response_type=code&client_id=72b3d019-5bc7-443d-a437-08f307cf06e2&redirect_uri=https://prd.cn-ccapi.hyundai.com:443/api/v1/user/oauth2/redirect",
        "token_url": "https://prd.cn-ccapi.hyundai.com/api/v1/user/oauth2/token",
        "redirect_url_final": "https://prd.cn-ccapi.hyundai.com:443/api/v1/user/oauth2/redirect",
        "success_selector": None,
        "user_agent": _DEFAULT_UA,
        "region_name": "China",
        "brand_name": "Hyundai",
    },
    # ── Australia ───────────────────────────────────────────
    "au_kia": {
        "client_id": "8acb778a-b918-4a8d-8624-73a0beb64289",
        "client_secret": "7ScMMm6fEYXdiEPCxaPaQmgeYdlUrfwoh4AfXGOzYIS2Cu9T",
        "login_url": "https://au-apigw.ccs.kia.com.au:8082/api/v1/user/oauth2/authorize?response_type=code&client_id=8acb778a-b918-4a8d-8624-73a0beb64289&redirect_uri=https://au-apigw.ccs.kia.com.au:8082/api/v1/user/oauth2/redirect",
        "token_url": "https://au-apigw.ccs.kia.com.au:8082/api/v1/user/oauth2/token",
        "redirect_url_final": "https://au-apigw.ccs.kia.com.au:8082/api/v1/user/oauth2/redirect",
        "success_selector": None,
        "user_agent": _DEFAULT_UA,
        "region_name": "Australia",
        "brand_name": "Kia",
    },
    "au_hyundai": {
        "client_id": "855c72df-dfd7-4230-ab03-67cbf902bb1c",
        "client_secret": "e6fbwHM32YNbhQl0pviaPp3rf4t3S6k91eceA3MJLdbdThCO",
        "login_url": "https://au-apigw.ccs.hyundai.com.au:8080/api/v1/user/oauth2/authorize?response_type=code&client_id=855c72df-dfd7-4230-ab03-67cbf902bb1c&redirect_uri=https://au-apigw.ccs.hyundai.com.au:8080/api/v1/user/oauth2/redirect",
        "token_url": "https://au-apigw.ccs.hyundai.com.au:8080/api/v1/user/oauth2/token",
        "redirect_url_final": "https://au-apigw.ccs.hyundai.com.au:8080/api/v1/user/oauth2/redirect",
        "success_selector": None,
        "user_agent": _DEFAULT_UA,
        "region_name": "Australia",
        "brand_name": "Hyundai",
    },
    # ── New Zealand ─────────────────────────────────────────
    "nz_kia": {
        "client_id": "4ab606a7-cea4-48a0-a216-ed9c14a4a38c",
        "client_secret": "0haFqXTkKktNKfzkxhZ0aku31i74g0yQFm5od2mz4LdI5mLY",
        "login_url": "https://au-apigw.ccs.kia.com.au:8082/api/v1/user/oauth2/authorize?response_type=code&client_id=4ab606a7-cea4-48a0-a216-ed9c14a4a38c&redirect_uri=https://au-apigw.ccs.kia.com.au:8082/api/v1/user/oauth2/redirect",
        "token_url": "https://au-apigw.ccs.kia.com.au:8082/api/v1/user/oauth2/token",
        "redirect_url_final": "https://au-apigw.ccs.kia.com.au:8082/api/v1/user/oauth2/redirect",
        "success_selector": None,
        "user_agent": _DEFAULT_UA,
        "region_name": "New Zealand",
        "brand_name": "Kia",
    },
    # ── India ───────────────────────────────────────────────
    "in_kia": {
        "client_id": "d0fe4855-7527-4be0-ab6e-a481216c705d",
        "client_secret": "SHoTtXpyfbYmP3XjNA6BrtlDglypPWj920PtKBJPfleHEYpU",
        "login_url": "https://prd.in-ccapi.kia.connected-car.io:8080/api/v1/user/oauth2/authorize?response_type=code&client_id=d0fe4855-7527-4be0-ab6e-a481216c705d&redirect_uri=https://prd.in-ccapi.kia.connected-car.io:8080/api/v1/user/oauth2/redirect",
        "token_url": "https://prd.in-ccapi.kia.connected-car.io:8080/api/v1/user/oauth2/token",
        "redirect_url_final": "https://prd.in-ccapi.kia.connected-car.io:8080/api/v1/user/oauth2/redirect",
        "success_selector": None,
        "user_agent": _DEFAULT_UA,
        "region_name": "India",
        "brand_name": "Kia",
    },
    "in_hyundai": {
        "client_id": "e5b3f6d0-7f83-43c9-aff3-a254db7af368",
        "client_secret": "5JFOCr6C24OfOzlDqZp7EwqrkL0Ww04UaxcDiE6Ud3qI5SE4",
        "login_url": "https://prd.in-ccapi.hyundai.connected-car.io:8080/api/v1/user/oauth2/authorize?response_type=code&client_id=e5b3f6d0-7f83-43c9-aff3-a254db7af368&redirect_uri=https://prd.in-ccapi.hyundai.connected-car.io:8080/api/v1/user/oauth2/redirect",
        "token_url": "https://prd.in-ccapi.hyundai.connected-car.io:8080/api/v1/user/oauth2/token",
        "redirect_url_final": "https://prd.in-ccapi.hyundai.connected-car.io:8080/api/v1/user/oauth2/redirect",
        "success_selector": None,
        "user_agent": _DEFAULT_UA,
        "region_name": "India",
        "brand_name": "Hyundai",
    },
    # ── Brazil ──────────────────────────────────────────────
    "br_hyundai": {
        "client_id": "03f7df9b-7626-4853-b7bd-ad1e8d722bd5",
        "client_secret": "yQz2bc6Cn8OovVOR7RDWwxTqVwWG3yKBYFDg0HsOXsyxyPlH",
        "login_url": "https://br-ccapi.hyundai.com.br/api/v1/user/oauth2/authorize?response_type=code&client_id=03f7df9b-7626-4853-b7bd-ad1e8d722bd5&redirect_uri=https://br-ccapi.hyundai.com.br/api/v1/user/oauth2/redirect",
        "token_url": "https://br-ccapi.hyundai.com.br/api/v1/user/oauth2/token",
        "redirect_url_final": "https://br-ccapi.hyundai.com.br/api/v1/user/oauth2/redirect",
        "success_selector": None,
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "region_name": "Brazil",
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
.vnc-frame { width: 100%; aspect-ratio: 16/10; border: none;
             border-radius: 10px; margin: 12px 0; background: var(--text); }
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

def get_token_thread(brand):
    config = BRAND_CONFIG[brand]
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
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(f"user-agent={config['user_agent']}")
        service = webdriver.ChromeService(executable_path="/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        # Remove webdriver flag from navigator
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        log(f"Opening {config['region_name']} {config['brand_name']} login page...")
        country = os.environ.get("COUNTRY", "DE").upper()
        login_url = config.get("login_url_template", "").format(country=country) if "login_url_template" in config else config["login_url"]
        driver.get(login_url)

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
        if config.get("success_selector"):
            wait.until(EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, config["success_selector"])),
                EC.url_contains("code=")))
        else:
            wait.until(EC.url_contains("code="))
        log("Login successful.", "ok")
        state["status"] = "processing"
        log("Retrieving authorization code...")

        # If config has a separate redirect_url, navigate to it and wait for code
        if config.get("redirect_url"):
            driver.get(config["redirect_url"])
            WebDriverWait(driver, 30).until(
                lambda d: "code=" in d.current_url or "error=" in d.current_url)

        current_url = driver.current_url
        if "error=" in current_url and "code=" not in current_url:
            error_match = re.search(r"error_description=([^&]+)", current_url)
            error_desc = error_match.group(1).replace("+", " ") if error_match else "Unknown OAuth error"
            state["status"] = "error"
            state["error"] = f"OAuth error: {error_desc}"
            log(state["error"], "err")
            return
        if "code=" not in current_url:
            state["status"] = "error"
            state["error"] = f"No auth code found in URL: {current_url[:120]}"
            log(state["error"], "err")
            return
        code_match = re.search(r"[?&]code=([^&]+)", current_url)
        if not code_match:
            state["status"] = "error"
            state["error"] = f"Could not extract auth code from URL: {current_url[:120]}"
            log(state["error"], "err")
            return
        log("Authorization code received.", "ok")
        log("Exchanging code for token...")
        data = {"grant_type": "authorization_code", "code": code_match.group(1),
                "redirect_uri": config["redirect_url_final"],
                "client_id": config["client_id"], "client_secret": config["client_secret"]}
        response = req_lib.post(config["token_url"], data=data, timeout=15)
        if response.status_code == 200:
            tokens = response.json()
            state["refresh_token"] = tokens.get("refresh_token", "N/A")
            state["access_token"] = tokens.get("access_token", "N/A")
            state["status"] = "success"
            log("Token generated successfully.", "ok")
            update_ha_sensor(brand)
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
    config = BRAND_CONFIG[brand]
    bt = f"{config['region_name']} {config['brand_name']}"
    s = state["status"]

    if s == "idle":
        has_creds = bool(os.environ.get("BLUELINK_USERNAME")) and bool(os.environ.get("BLUELINK_PASSWORD"))
        creds_note = ("Credentials are configured and will be filled in automatically. "
                      "You only need to click the Sign In button.") if has_creds else (
                      "No credentials configured. You will need to enter them manually in the browser. "
                      "Tip: Set username and password in the addon configuration for auto-fill.")
        default_brand = os.environ.get("BRAND", "auto").lower()
        default_brand = BRAND_ALIASES.get(default_brand, default_brand)
        brand_fixed = default_brand in BRAND_CONFIG
        if brand_fixed:
            brand_html = f'<input type="hidden" name="brand" value="{default_brand}">'
        else:
            # Build grouped options from BRAND_CONFIG
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
        return render(f"""
<div class="card">
    <div class="card-title">Generate Refresh Token</div>
    <p style="margin-bottom: 12px; color: var(--text-secondary); font-size: 14px;">
        A Chromium browser will open in the background. You can interact with it
        through the embedded viewer below to complete the {"" if brand_fixed else ""}Bluelink login.
    </p>
    <div class="notice notice-info">{creds_note}</div>
    <form method="POST" action="/start">
        {brand_html}
        <button type="submit" class="btn btn-primary">Start token generation</button>
    </form>
</div>""")

    elif s == "waiting_login":
        env_user = os.environ.get("BLUELINK_USERNAME", "")
        env_pass = os.environ.get("BLUELINK_PASSWORD", "")
        return render(f"""
<div class="card">
    <div class="card-title">Sign in to {bt} Bluelink</div>
    <div class="notice notice-warning">
        Waiting for login. Use your {bt} Bluelink credentials (same as the mobile app).
        The session will time out after 5 minutes.
    </div>
    <div class="log" id="log-box">{format_log()}</div>
    <hr class="divider">
    <div class="section-label">Auto-fill credentials</div>
    <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:12px;">
        <input type="text" id="login-user" placeholder="E-Mail / Username"
               value="{html_lib.escape(env_user)}" style="width:100%;">
        <input type="password" id="login-pass" placeholder="Password"
               value="{html_lib.escape(env_pass)}" style="width:100%;">
        <div class="actions">
            <button class="btn btn-primary" onclick="doFillAndLogin()" id="fill-btn">Fill &amp; Login</button>
            <button class="btn btn-secondary" onclick="doFillOnly()">Fill only</button>
        </div>
    </div>
    <p class="hint">Fills the credentials into the browser below and optionally clicks Sign In.
        You may still need to solve a CAPTCHA manually.</p>
    <div id="fill-result"></div>
    <hr class="divider">
    <div class="section-label">Remote browser</div>
    <iframe src="/novnc" class="vnc-frame" id="vnc"></iframe>
</div>
<script>
function doFillAndLogin() {{ _doFill(true); }}
function doFillOnly() {{ _doFill(false); }}
function _doFill(clickLogin) {{
    var btn = document.getElementById('fill-btn');
    var res = document.getElementById('fill-result');
    btn.disabled = true; btn.textContent = 'Filling...';
    res.innerHTML = '';
    fetch('/api/autologin', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
            username: document.getElementById('login-user').value,
            password: document.getElementById('login-pass').value,
            click_login: clickLogin
        }})
    }}).then(function(r){{ return r.json(); }}).then(function(d) {{
        btn.disabled = false; btn.textContent = 'Fill & Login';
        if (d.ok) {{
            res.innerHTML = '<div class="notice notice-success">' + d.message + '</div>';
        }} else {{
            res.innerHTML = '<div class="notice notice-error">' + d.error + '</div>';
        }}
    }}).catch(function(e) {{
        btn.disabled = false; btn.textContent = 'Fill & Login';
        res.innerHTML = '<div class="notice notice-error">Request failed</div>';
    }});
}}
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
        <button type="submit" class="btn btn-primary">Try again</button>
    </form>
</div>""")

    return render('<div class="card">Unknown state</div>')

@app.route("/start", methods=["POST"])
def start():
    chosen_brand = request.form.get("brand", "").lower()
    chosen_brand = BRAND_ALIASES.get(chosen_brand, chosen_brand)
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

@app.route("/api/autologin", methods=["POST"])
def api_autologin():
    """Fill username + password into the browser and optionally click login."""
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")
    click_login = data.get("click_login", False)
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"})
    xenv = {**os.environ, "DISPLAY": ":99"}
    try:
        # Find and click the email/username field
        # Use xdotool to search for the input field by tab-navigating
        # First, click somewhere in the browser to focus it
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], env=xenv, timeout=5)
        time.sleep(0.3)

        # Tab to first input field (email) — press Tab a few times from the top
        # More reliable: use Ctrl+L to focus address bar, then Tab into page
        subprocess.run(["xdotool", "key", "--clearmodifiers", "F6"], env=xenv, timeout=5)
        time.sleep(0.2)
        # Tab into the page content
        for _ in range(3):
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Tab"], env=xenv, timeout=5)
            time.sleep(0.1)

        # Select all + type username
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+a"], env=xenv, timeout=5)
        time.sleep(0.1)
        subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "12", username],
                       env=xenv, timeout=10)
        time.sleep(0.3)

        # Tab to password field
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Tab"], env=xenv, timeout=5)
        time.sleep(0.2)

        # Type password
        subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "12", password],
                       env=xenv, timeout=10)
        time.sleep(0.3)

        msg = "Credentials filled."

        if click_login:
            # Press Enter to submit the form
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], env=xenv, timeout=5)
            msg = "Credentials filled and login submitted."

        return jsonify({"ok": True, "message": msg})
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

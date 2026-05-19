"""HA evcc Token Transfer Module.

Handles automatic token transfer from bluelink-refresh-token to evcc.
"""

import os

import requests as req_lib
import urllib3

# Suppress InsecureRequestWarning for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _auto_evcc_transfer(evcc_url, evcc_password, state, log_fn=None):
    """Auto-transfer refresh token to evcc after successful login.

    Args:
        evcc_url: evcc base URL
        evcc_password: evcc admin password
        state: application state dict with vehicles and tokens
        log_fn: optional logging callback (msg, level)
    """
    def _log(msg, level="info"):
        if log_fn:
            log_fn(msg, level)

    try:
        _log(f"Auto-start: connecting to evcc ({evcc_url})...")
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
            _log(f"Auto-start: could not fetch evcc vehicles ({resp.status_code})", "warn")
            return
        data = resp.json()
        all_vehicles = data.get("result", data) if isinstance(data, dict) else data
        if not isinstance(all_vehicles, list):
            all_vehicles = []
        vehicles = [v for v in all_vehicles
                    if isinstance(v, dict) and any(t in str(v.get("config", v)).lower()
                           for t in ("hyundai", "kia", "bluelink"))]
        if not vehicles:
            _log("Auto-start: no Hyundai/Kia vehicles found in evcc", "warn")
            return
        _log(f"Auto-start: found {len(vehicles)} vehicle(s) in evcc", "ok")
        # Build maps for token matching:
        # 1. username → token (precise matching by account)
        # 2. brand → token (fallback for single-vehicle setups)
        token_by_username = {}
        token_by_brand = {}
        for sv in state.get("vehicles", []):
            if sv.get("status") == "ok" and sv.get("refresh_token"):
                username = sv.get("username", "").lower()
                brand_name = sv.get("brand_name", "").lower()
                if username:
                    token_by_username[username] = sv["refresh_token"]
                token_by_brand[brand_name] = sv["refresh_token"]
        if not token_by_brand:
            # Fallback: use the last generated token for all
            token_by_brand["kia"] = state.get("refresh_token", "")
            token_by_brand["hyundai"] = state.get("refresh_token", "")
        _log(f"Auto-start: tokens available for {len(token_by_username)} account(s)")

        for v in vehicles:
            vid = v["id"]
            title = v.get("config", {}).get("title", f"Vehicle {vid}")
            try:
                # Get current config
                cfg_resp = session.get(f"{evcc_url}/api/config/devices/vehicle/{vid}", timeout=10)
                if cfg_resp.status_code != 200:
                    _log(f"Auto-start: could not fetch config for {title}", "warn")
                    continue
                vehicle_data = cfg_resp.json()
                cfg = vehicle_data.get("config", {})
                # Find the right token: first try username match, then brand fallback
                evcc_user = cfg.get("user", "").lower()
                tmpl = cfg.get("template", "").lower()
                token = None
                if evcc_user and evcc_user in token_by_username:
                    token = token_by_username[evcc_user]
                else:
                    token = token_by_brand.get(tmpl, token_by_brand.get("kia", token_by_brand.get("hyundai", "")))
                if not token:
                    _log(f"Auto-start: no token available for {title} (template: {tmpl})", "warn")
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
                    _log(f"Auto-start: token sent to {title}", "ok")
                else:
                    _log(f"Auto-start: failed to update {title} ({resp.status_code}): {resp.text[:200]}", "warn")
            except (req_lib.exceptions.ConnectionError, ConnectionError):
                # Connection error during update is OK — evcc may be restarting
                _log(f"Auto-start: token sent to {title} (connection closed, evcc may be restarting)", "ok")
            except Exception as e:
                _log(f"Auto-start: error updating {title}: {e}", "warn")
        # Restart evcc
        _log("Auto-start: restarting evcc...")
        supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
        if supervisor_token:
            try:
                resp = req_lib.post("http://supervisor/addons/a0d7b954_evcc/restart",
                                    headers={"Authorization": f"Bearer {supervisor_token}"},
                                    timeout=30)
                if resp.status_code == 200:
                    _log("Auto-start: evcc restarted via HA Supervisor", "ok")
                    return
            except Exception:
                pass
        try:
            session.post(f"{evcc_url}/api/system/shutdown", timeout=10)
            _log("Auto-start: evcc restart triggered", "ok")
        except Exception:
            _log("Auto-start: could not restart evcc automatically", "warn")
    except Exception as e:
        _log(f"Auto-start: evcc transfer error: {e}", "warn")


def evcc_get_vehicles(evcc_url, password):
    """Login to evcc and return list of Hyundai/Kia vehicles.

    Returns: dict with 'ok', 'vehicles' or 'error' keys
    """
    if not evcc_url:
        return {"ok": False, "error": "No evcc URL provided"}
    try:
        session = req_lib.Session()
        session.verify = False
        # Check if auth is required
        auth_resp = session.get(f"{evcc_url}/api/auth/status", timeout=10)
        needs_auth = auth_resp.status_code == 200 and auth_resp.text.strip() == "false"
        if needs_auth:
            if not password:
                return {"ok": False, "error": "evcc requires admin password"}
            resp = session.post(f"{evcc_url}/api/auth/login",
                                json={"password": password}, timeout=10)
            if resp.status_code == 401:
                return {"ok": False, "error": "Invalid admin password"}
            if resp.status_code != 200:
                return {"ok": False, "error": f"Login failed ({resp.status_code})"}
        # Get vehicles
        resp = session.get(f"{evcc_url}/api/config/devices/vehicle", timeout=10)
        if resp.status_code == 401:
            return {"ok": False, "error": "Authentication required — please enter your evcc admin password"}
        if resp.status_code != 200:
            return {"ok": False, "error": f"Could not fetch vehicles ({resp.status_code})"}
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
        return {"ok": True, "vehicles": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def evcc_update_vehicle(evcc_url, password, vehicle_id, token):
    """Update a vehicle's password (refresh token) in evcc.

    Returns: dict with 'ok' or 'error' keys
    """
    if not all([evcc_url, vehicle_id, token]):
        return {"ok": False, "error": "Missing parameters"}
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
                return {"ok": False, "error": f"Login failed ({resp.status_code})"}
        # Get current vehicle config
        resp = session.get(f"{evcc_url}/api/config/devices/vehicle/{vehicle_id}", timeout=10)
        if resp.status_code != 200:
            return {"ok": False, "error": f"Could not fetch vehicle ({resp.status_code})"}
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
            return {"ok": False, "error": f"Token test failed ({resp.status_code}): {resp.text[:200]}"}
        # Apply update
        resp = session.put(f"{evcc_url}/api/config/devices/vehicle/{vehicle_id}",
                           json=payload, timeout=15)
        if resp.status_code != 200:
            return {"ok": False, "error": f"Update failed ({resp.status_code}): {resp.text[:200]}"}
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def evcc_restart(evcc_url, password):
    """Restart evcc.

    Returns: dict with 'ok' or 'error' keys
    """
    if not evcc_url:
        return {"ok": False, "error": "No evcc URL provided"}

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
                        return {"ok": True}
                    return {"ok": False, "error": f"Supervisor restart failed ({resp.status_code})"}
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
            return {"ok": True}
        return {"ok": False, "error": f"Restart failed ({resp.status_code})"}
    except req_lib.exceptions.ConnectionError:
        # Connection error is expected — evcc is shutting down
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

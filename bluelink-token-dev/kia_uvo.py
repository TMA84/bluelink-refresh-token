"""HA kia_uvo Token Transfer Module.

Handles automatic token transfer from bluelink-refresh-token to the kia_uvo
Home Assistant integration via the HA REST API. After generating a refresh token,
this module can programmatically drive the kia_uvo reconfigure flow to update
credentials — no volume mounts or manual copying required.

This module mirrors the existing _auto_evcc_transfer pattern: functions are called
after successful token generation, communicate over HTTP, and handle errors
gracefully without disrupting the main flow.
"""

import os

import requests as req_lib
import urllib3

# Suppress InsecureRequestWarning for self-signed HA certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _kia_uvo_config() -> dict | None:
    """Read and validate environment variables for kia_uvo transfer.

    Returns config dict if kia_uvo transfer is enabled, None otherwise.

    Priority for HA connection:
        1. SUPERVISOR_TOKEN (automatic in HA addon) → http://supervisor/core
        2. HA_URL + HA_TOKEN (manual config)

    Returns:
        dict with keys ha_url, ha_token, enabled when transfer is enabled.
        None when transfer should be skipped.
    """
    ha_url = os.environ.get("HA_URL", "").strip()
    ha_token = os.environ.get("HA_TOKEN", "").strip()
    ha_transfer = os.environ.get("HA_KIA_UVO_TRANSFER", "").strip().lower()

    # Priority 1: SUPERVISOR_TOKEN (always works in HA addon, no config needed)
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    if supervisor_token:
        ha_url = "http://supervisor/core"
        ha_token = supervisor_token
        print(f"[KIA_UVO] Using SUPERVISOR_TOKEN with {ha_url}", flush=True)
    elif not ha_url or not ha_token:
        # No supervisor token and no manual config
        return None

    # Strip trailing slash from HA_URL
    ha_url = ha_url.rstrip("/")

    # Explicit disable
    if ha_transfer == "false":
        return None

    return {
        "ha_url": ha_url,
        "ha_token": ha_token,
        "enabled": True,
    }


def _detect_kia_uvo_entries(ha_url: str, ha_token: str) -> list[dict]:
    """Query HA for kia_uvo config entries.

    Sends a GET request to the Home Assistant REST API to discover any
    installed kia_uvo integration config entries.

    Returns list of config entry dicts with at least 'entry_id' and 'data' fields.
    Returns empty list on any error (logged internally).

    Args:
        ha_url: Home Assistant base URL (no trailing slash).
        ha_token: Long-Lived Access Token for HA REST API.

    Returns:
        List of config entry dicts on success, empty list on any error.
    """
    # Determine the correct URL based on whether we're using supervisor proxy
    if "supervisor" in ha_url:
        # Supervisor proxy: http://supervisor/core/api/...
        url = f"{ha_url}/api/config/config_entries/entry?domain=kia_uvo"
    else:
        url = f"{ha_url}/api/config/config_entries/entry?domain=kia_uvo"

    headers = {"Authorization": f"Bearer {ha_token}"}

    try:
        print(f"[KIA_UVO] Detecting entries: GET {url}", flush=True)
        resp = req_lib.get(url, headers=headers, timeout=(10, 30), verify=False)
        print(f"[KIA_UVO] Detection response: HTTP {resp.status_code}, body length: {len(resp.text)}", flush=True)
        resp.raise_for_status()
        entries = resp.json()
        print(f"[KIA_UVO] Detection result: {len(entries)} entries found", flush=True)
        if entries:
            for e in entries:
                print(f"[KIA_UVO]   Entry: {e.get('entry_id', '?')} — {e.get('title', '?')}", flush=True)
        return entries
    except req_lib.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        print(f"[KIA_UVO] HTTP error detecting kia_uvo entries: {status}", flush=True)
        return []
    except req_lib.exceptions.ConnectionError as e:
        print(f"[KIA_UVO] Connection error detecting kia_uvo entries: {e}", flush=True)
        return []
    except req_lib.exceptions.Timeout:
        print("[KIA_UVO] Timeout detecting kia_uvo entries: HA did not respond within 10s", flush=True)
        return []
    except Exception as e:
        print(f"[KIA_UVO] Unexpected error detecting kia_uvo entries: {type(e).__name__}: {e}", flush=True)
        return []


def _extract_username_from_entry(entry: dict) -> str | None:
    """Extract username from a config entry.

    The HA REST API does NOT return the 'data' field in config entry responses
    (for security reasons — it contains passwords). Instead, we extract the
    username from the 'title' field which has the format:
        "Kia Europe user@example.com"
        "Hyundai Europe user@example.com"

    Falls back to data.username if available (e.g. in test scenarios).

    Args:
        entry: A config entry dict from the HA API.

    Returns:
        The extracted username/email, or None if not found.
    """
    # Try data.username first (available in tests or future API versions)
    try:
        username = entry["data"]["username"]
        if username:
            return username
    except (KeyError, TypeError):
        pass

    # Extract from title: "Brand Region username@email.com"
    title = entry.get("title", "")
    if "@" in title:
        # The email is typically the last space-separated token
        parts = title.strip().split()
        for part in reversed(parts):
            if "@" in part:
                return part

    return None


def _match_entries_to_vehicles(
    entries: list[dict],
    vehicles: list[dict],
) -> list[tuple[dict, dict]]:
    """Match HA config entries to generated vehicles by username.

    Extracts username from entry title or data.username, then matches
    against vehicle username fields.

    Matching logic:
        - Extract username from entry (title or data.username)
        - Compare with vehicle["username"] (case-sensitive)
        - Skip entries where username cannot be extracted
        - Each entry matches at most one vehicle (first match wins)

    Args:
        entries: List of HA config entry dicts from detection.
        vehicles: List of vehicle credential dicts from VEHICLES_JSON.

    Returns:
        List of (entry, vehicle) tuples for matched pairs.
    """
    matched: list[tuple[dict, dict]] = []

    for entry in entries:
        entry_username = _extract_username_from_entry(entry)
        if not entry_username:
            continue

        # Find matching vehicle by username (case-sensitive)
        for vehicle in vehicles:
            vehicle_username = vehicle.get("username")
            if vehicle_username is not None and vehicle_username == entry_username:
                matched.append((entry, vehicle))
                break

    return matched


def _reconfigure_kia_uvo_entry(
    ha_url: str,
    ha_token: str,
    entry_id: str,
    username: str,
    password: str,
    pin: str,
    region: int = 2,
    brand: int = 1,
) -> bool:
    """Drive the kia_uvo reconfigure flow for a single config entry.

    Executes a 4-step reconfigure flow against the Home Assistant REST API:
        Step 1: Initiate reconfigure flow for the given entry
        Step 2: Select "reauth" as the reconfigure choice
        Step 3: Submit region/brand configuration
        Step 4: Submit credentials (username, password, pin)

    Each step validates the response contains a flow_id and expected structure
    before proceeding to the next step.

    Args:
        ha_url: Home Assistant base URL (no trailing slash).
        ha_token: Long-Lived Access Token for HA REST API.
        entry_id: The config entry ID to reconfigure.
        username: Account username/email for kia_uvo.
        password: Account password for kia_uvo.
        pin: Vehicle PIN for kia_uvo.
        region: Region code from entry data (default 2).
        brand: Brand code from entry data (default 1).

    Returns:
        True on successful completion of all 4 steps, False on any failure.
    """
    headers = {"Authorization": f"Bearer {ha_token}"}
    timeout = 30

    # Step 1: Initiate reconfigure flow
    try:
        resp = req_lib.post(
            f"{ha_url}/api/config/config_entries/flow",
            headers=headers,
            json={"handler": "kia_uvo", "entry_id": entry_id},
            timeout=timeout,
            verify=False,
        )
        resp.raise_for_status()
    except req_lib.exceptions.Timeout:
        print(f"[KIA_UVO] Timeout initiating reconfigure flow for entry {entry_id}", flush=True)
        return False
    except req_lib.exceptions.ConnectionError:
        print(f"[KIA_UVO] Connection error initiating reconfigure flow for entry {entry_id}", flush=True)
        return False
    except req_lib.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        print(f"[KIA_UVO] HTTP {status} initiating reconfigure flow for entry {entry_id}", flush=True)
        return False
    except Exception as e:
        print(f"[KIA_UVO] Unexpected error initiating reconfigure flow: {e}", flush=True)
        return False

    try:
        step1_data = resp.json()
    except Exception:
        print(f"[KIA_UVO] Malformed JSON in step 1 response for entry {entry_id}", flush=True)
        return False

    flow_id = step1_data.get("flow_id")
    if not flow_id:
        print(f"[KIA_UVO] Missing flow_id in step 1 response for entry {entry_id} (type: {step1_data.get('type', 'unknown')})", flush=True)
        return False

    # Step 2: Select reauth choice
    try:
        resp = req_lib.post(
            f"{ha_url}/api/config/config_entries/flow/{flow_id}",
            headers=headers,
            json={"reconfigure_choice": "reauth"},
            timeout=timeout,
            verify=False,
        )
        resp.raise_for_status()
    except req_lib.exceptions.Timeout:
        print(f"[KIA_UVO] Timeout at step 2 (reauth choice) for flow {flow_id}", flush=True)
        return False
    except req_lib.exceptions.ConnectionError:
        print(f"[KIA_UVO] Connection error at step 2 (reauth choice) for flow {flow_id}", flush=True)
        return False
    except req_lib.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        print(f"[KIA_UVO] HTTP {status} at step 2 (reauth choice) for flow {flow_id}", flush=True)
        return False
    except Exception as e:
        print(f"[KIA_UVO] Unexpected error at step 2: {e}", flush=True)
        return False

    try:
        step2_data = resp.json()
    except Exception:
        print(f"[KIA_UVO] Malformed JSON in step 2 response for flow {flow_id}", flush=True)
        return False

    step2_flow_id = step2_data.get("flow_id")
    if not step2_flow_id:
        print(f"[KIA_UVO] Missing flow_id in step 2 response (type: {step2_data.get('type', 'unknown')})", flush=True)
        return False

    # Step 3: Submit region/brand (HA expects string values)
    try:
        resp = req_lib.post(
            f"{ha_url}/api/config/config_entries/flow/{flow_id}",
            headers=headers,
            json={"region": str(region), "brand": str(brand)},
            timeout=timeout,
            verify=False,
        )
        resp.raise_for_status()
    except req_lib.exceptions.Timeout:
        print(f"[KIA_UVO] Timeout at step 3 (region/brand) for flow {flow_id}", flush=True)
        return False
    except req_lib.exceptions.ConnectionError:
        print(f"[KIA_UVO] Connection error at step 3 (region/brand) for flow {flow_id}", flush=True)
        return False
    except req_lib.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        print(f"[KIA_UVO] HTTP {status} at step 3 (region/brand) for flow {flow_id}", flush=True)
        return False
    except Exception as e:
        print(f"[KIA_UVO] Unexpected error at step 3: {e}", flush=True)
        return False

    try:
        step3_data = resp.json()
    except Exception:
        print(f"[KIA_UVO] Malformed JSON in step 3 response for flow {flow_id}", flush=True)
        return False

    step3_flow_id = step3_data.get("flow_id")
    if not step3_flow_id:
        print(f"[KIA_UVO] Missing flow_id in step 3 response (type: {step3_data.get('type', 'unknown')})", flush=True)
        return False

    # Step 4: Submit credentials
    try:
        resp = req_lib.post(
            f"{ha_url}/api/config/config_entries/flow/{flow_id}",
            headers=headers,
            json={"username": username, "password": password, "pin": pin},
            timeout=timeout,
            verify=False,
        )
        resp.raise_for_status()
    except req_lib.exceptions.Timeout:
        print(f"[KIA_UVO] Timeout at step 4 (credentials) for flow {flow_id}", flush=True)
        return False
    except req_lib.exceptions.ConnectionError:
        print(f"[KIA_UVO] Connection error at step 4 (credentials) for flow {flow_id}", flush=True)
        return False
    except req_lib.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        print(f"[KIA_UVO] HTTP {status} at step 4 (credentials) for flow {flow_id}", flush=True)
        return False
    except Exception as e:
        print(f"[KIA_UVO] Unexpected error at step 4: {e}", flush=True)
        return False

    try:
        step4_data = resp.json()
    except Exception:
        print(f"[KIA_UVO] Malformed JSON in step 4 response for flow {flow_id}", flush=True)
        return False

    # Success detection: HA returns type="abort" with reason="reconfigure_successful"
    # or type="create_entry" on success
    step4_type = step4_data.get("type", "")
    step4_reason = step4_data.get("reason", "")

    if step4_type == "abort" and step4_reason == "reconfigure_successful":
        print(f"[KIA_UVO] Reconfigure flow completed successfully for entry {entry_id}", flush=True)
        return True
    elif step4_type == "create_entry":
        print(f"[KIA_UVO] Reconfigure flow completed successfully for entry {entry_id}", flush=True)
        return True
    elif step4_type == "abort":
        print(f"[KIA_UVO] Reconfigure flow aborted for entry {entry_id}: {step4_reason}", flush=True)
        return False
    elif step4_data.get("errors"):
        print(f"[KIA_UVO] Reconfigure flow errors for entry {entry_id}: {step4_data['errors']}", flush=True)
        return False

    # If we got a flow_id back, it might be asking for more steps (unexpected)
    step4_flow_id = step4_data.get("flow_id")
    if not step4_flow_id:
        print(f"[KIA_UVO] Missing flow_id in step 4 response (type: {step4_data.get('type', 'unknown')})", flush=True)
        return False

    print(f"[KIA_UVO] Reconfigure flow completed for entry {entry_id} (response: {step4_type})", flush=True)
    return True


def _setup_kia_uvo_entry(
    ha_url: str,
    ha_token: str,
    username: str,
    password: str,
    pin: str,
    region: str = "1",
    brand: str = "1",
) -> bool:
    """Run the initial kia_uvo setup flow (when no config entry exists yet).

    This is a 2-step flow:
        Step 1: POST /api/config/config_entries/flow (without entry_id) → region/brand
        Step 2: POST /api/config/config_entries/flow/{flow_id} → credentials

    Args:
        ha_url: Home Assistant base URL (no trailing slash).
        ha_token: Long-Lived Access Token or SUPERVISOR_TOKEN.
        username: Account username/email for kia_uvo.
        password: Refresh token (used as password for kia_uvo).
        pin: Vehicle PIN.
        region: Region code as string (default "1" = Europe).
        brand: Brand code as string (default "1" = Kia).

    Returns:
        True on successful setup, False on any failure.
    """
    headers = {"Authorization": f"Bearer {ha_token}"}
    timeout = 30

    # Step 1: Initiate setup flow (no entry_id = new setup)
    try:
        resp = req_lib.post(
            f"{ha_url}/api/config/config_entries/flow",
            headers=headers,
            json={"handler": "kia_uvo"},
            timeout=timeout,
            verify=False,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[KIA_UVO] Error initiating setup flow: {e}", flush=True)
        return False

    try:
        step1_data = resp.json()
    except Exception:
        print(f"[KIA_UVO] Malformed JSON in setup step 1 response", flush=True)
        return False

    flow_id = step1_data.get("flow_id")
    if not flow_id:
        print(f"[KIA_UVO] Missing flow_id in setup step 1 (type: {step1_data.get('type', 'unknown')})", flush=True)
        return False

    # Step 2: Submit region/brand
    try:
        resp = req_lib.post(
            f"{ha_url}/api/config/config_entries/flow/{flow_id}",
            headers=headers,
            json={"region": str(region), "brand": str(brand)},
            timeout=timeout,
            verify=False,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[KIA_UVO] Error at setup step 2 (region/brand): {e}", flush=True)
        return False

    try:
        step2_data = resp.json()
    except Exception:
        print(f"[KIA_UVO] Malformed JSON in setup step 2 response", flush=True)
        return False

    if not step2_data.get("flow_id"):
        print(f"[KIA_UVO] Missing flow_id in setup step 2 (type: {step2_data.get('type', 'unknown')})", flush=True)
        return False

    # Step 3: Submit credentials
    try:
        resp = req_lib.post(
            f"{ha_url}/api/config/config_entries/flow/{flow_id}",
            headers=headers,
            json={"username": username, "password": password, "pin": pin},
            timeout=timeout,
            verify=False,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[KIA_UVO] Error at setup step 3 (credentials): {e}", flush=True)
        return False

    try:
        step3_data = resp.json()
    except Exception:
        print(f"[KIA_UVO] Malformed JSON in setup step 3 response", flush=True)
        return False

    # Success detection
    step3_type = step3_data.get("type", "")
    step3_reason = step3_data.get("reason", "")

    if step3_type == "create_entry":
        print(f"[KIA_UVO] Initial setup completed successfully!", flush=True)
        return True
    elif step3_type == "abort" and "success" in step3_reason:
        print(f"[KIA_UVO] Initial setup completed successfully!", flush=True)
        return True
    elif step3_type == "abort":
        print(f"[KIA_UVO] Setup aborted: {step3_reason}", flush=True)
        return False
    elif step3_data.get("errors"):
        print(f"[KIA_UVO] Setup errors: {step3_data['errors']}", flush=True)
        return False

    print(f"[KIA_UVO] Setup completed (response type: {step3_type})", flush=True)
    return True


def _auto_kia_uvo_transfer(vehicles: list[dict], log_fn=None):
    """Main entry point for kia_uvo token transfer.

    Called after successful token generation. Orchestrates the full transfer
    flow: configuration check, entry detection, vehicle matching, and
    reconfigure flow execution for each matched pair.

    This function never raises exceptions — all errors are caught and logged
    to ensure the caller is never disrupted.

    Args:
        vehicles: List of vehicle config dicts that had successful token generation.
                  Each has: brand, username, password, and optionally pin.
        log_fn: Optional callback for Web UI logging. Signature: log_fn(msg, level).
                If None, only prints to stdout.
    """
    def _log(msg, level="info"):
        print(f"[KIA_UVO] {msg}", flush=True)
        if log_fn:
            log_fn(f"kia_uvo: {msg}", level)

    try:
        # Step 1: Get configuration
        config = _kia_uvo_config()
        if config is None:
            _log("Transfer skipped: not configured (HA_URL/HA_TOKEN missing or disabled)")
            return

        ha_url = config["ha_url"]
        ha_token = config["ha_token"]

        _log(f"Starting token transfer to {ha_url}...")

        # Step 2: Detect kia_uvo config entries
        entries = _detect_kia_uvo_entries(ha_url, ha_token)

        # Map vehicle brands to kia_uvo region/brand codes
        BRAND_TO_REGION = {
            "eu_kia": ("1", "1"),       # Europe, Kia
            "eu_hyundai": ("1", "2"),   # Europe, Hyundai
        }

        if not entries:
            # No entries found — try initial setup for each vehicle
            _log("No existing kia_uvo entries found — running initial setup...")
            success_count = 0
            fail_count = 0

            for vehicle in vehicles:
                username = vehicle.get("username", "")
                password = vehicle.get("password", "")
                pin = vehicle.get("pin") or os.environ.get("HA_KIA_UVO_PIN", "")
                vehicle_brand = vehicle.get("brand", "eu_kia")
                region, brand = BRAND_TO_REGION.get(vehicle_brand, ("1", "1"))

                result = _setup_kia_uvo_entry(
                    ha_url=ha_url,
                    ha_token=ha_token,
                    username=username,
                    password=password,
                    pin=pin,
                    region=region,
                    brand=brand,
                )

                if result:
                    success_count += 1
                    _log(f"Initial setup completed for {username}", "ok")
                else:
                    fail_count += 1
                    _log(f"Initial setup failed for {username}", "err")

            if fail_count == 0 and success_count > 0:
                _log(f"Setup complete: {success_count} succeeded", "ok")
            elif success_count > 0:
                _log(f"Setup complete: {success_count} succeeded, {fail_count} failed", "warn")
            else:
                _log("Setup failed for all vehicles", "err")
            return

        # Step 3: Match entries to vehicles
        matches = _match_entries_to_vehicles(entries, vehicles)
        if not matches:
            _log("Transfer skipped: no matching vehicles found for detected entries", "warn")
            return

        _log(f"Found {len(matches)} matching entry/vehicle pair(s)")

        # Step 4: Reconfigure each matched entry
        success_count = 0
        fail_count = 0

        for entry, vehicle in matches:
            entry_id = entry.get("entry_id", "unknown")
            username = vehicle.get("username", "")

            # Resolve PIN: vehicle pin field first, then env var fallback
            pin = vehicle.get("pin") or os.environ.get("HA_KIA_UVO_PIN", "")

            # Determine region/brand from vehicle brand config
            vehicle_brand = vehicle.get("brand", "eu_kia")
            region, brand = BRAND_TO_REGION.get(vehicle_brand, ("1", "1"))

            password = vehicle.get("password", "")

            result = _reconfigure_kia_uvo_entry(
                ha_url=ha_url,
                ha_token=ha_token,
                entry_id=entry_id,
                username=username,
                password=password,
                pin=pin,
                region=region,
                brand=brand,
            )

            if result:
                success_count += 1
                _log(f"Token transferred to kia_uvo ({username})", "ok")
            else:
                fail_count += 1
                _log(f"Failed to transfer token for {username}", "err")

        if fail_count == 0:
            _log(f"Transfer complete: {success_count} succeeded", "ok")
        else:
            _log(f"Transfer complete: {success_count} succeeded, {fail_count} failed", "warn")

    except Exception as e:
        # Top-level catch: never crash the caller
        _log(f"Unexpected error: {e}", "err")

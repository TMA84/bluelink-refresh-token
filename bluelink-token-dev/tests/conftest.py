"""Shared test fixtures for bluelink-token-dev tests.

Provides reusable fixtures for mocking HTTP responses, sample config entries,
vehicle configurations, and flow responses used across unit and property tests.
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure the parent directory (bluelink-token-dev/) is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# --- Environment variable keys used by kia_uvo ---
_HA_ENV_KEYS = [
    "HA_URL",
    "HA_TOKEN",
    "HA_KIA_UVO_TRANSFER",
    "HA_KIA_UVO_PIN",
]


@pytest.fixture
def sample_config_entries():
    """Sample HA config entry dicts for kia_uvo integration."""
    return [
        {
            "entry_id": "abc123def456",
            "domain": "kia_uvo",
            "title": "Kia e-Niro",
            "data": {"username": "user@example.com", "region": 2, "brand": 1},
        },
        {
            "entry_id": "xyz789ghi012",
            "domain": "kia_uvo",
            "title": "Kia EV6",
            "data": {"username": "other@example.com", "region": 2, "brand": 1},
        },
    ]


@pytest.fixture
def sample_vehicles():
    """Sample vehicle config dicts with credentials."""
    return [
        {"brand": "eu_kia", "username": "user@example.com", "password": "pass123", "pin": "1234"},
        {"brand": "eu_kia", "username": "other@example.com", "password": "pass456"},
    ]


@pytest.fixture
def sample_flow_responses():
    """Mock responses for each step of the kia_uvo reconfigure flow."""
    return {
        "step1": {"flow_id": "flow_test_123", "type": "form", "step_id": "reconfigure_confirm"},
        "step2": {"flow_id": "flow_test_123", "type": "form", "step_id": "region"},
        "step3": {"flow_id": "flow_test_123", "type": "form", "step_id": "credentials"},
        "step4": {"flow_id": "flow_test_123", "type": "create_entry", "result": "success"},
    }


@pytest.fixture
def mock_ha_env(monkeypatch):
    """Set up HA environment variables for testing.

    Configures:
        HA_URL=http://homeassistant.local:8123
        HA_TOKEN=test_long_lived_token
        HA_KIA_UVO_TRANSFER=true
        HA_KIA_UVO_PIN=0000
    """
    monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
    monkeypatch.setenv("HA_TOKEN", "test_long_lived_token")
    monkeypatch.setenv("HA_KIA_UVO_TRANSFER", "true")
    monkeypatch.setenv("HA_KIA_UVO_PIN", "0000")


@pytest.fixture
def clean_env(monkeypatch):
    """Clear all HA-related environment variables for test isolation.

    Removes HA_URL, HA_TOKEN, HA_KIA_UVO_TRANSFER, and HA_KIA_UVO_PIN
    from the environment to ensure tests start from a clean state.
    """
    for key in _HA_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

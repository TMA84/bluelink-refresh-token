"""Unit tests for kia_uvo integration point in web.py.

Tests that kia_uvo transfer is called correctly after token generation,
that failures don't block evcc transfer, and that both transfers execute
independently.

Validates: Requirements 4.3, 4.4
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path so we can import web module functions
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestKiaUvoTransferEnabled:
    """Tests for _kia_uvo_transfer_enabled() helper in web.py."""

    def test_returns_true_when_config_present(self):
        """_kia_uvo_transfer_enabled returns True when _kia_uvo_config returns a dict.

        Validates: Requirements 4.3
        """
        mock_config = {"ha_url": "http://ha.local:8123", "ha_token": "tok", "enabled": True}
        with patch("web._kia_uvo_config", return_value=mock_config):
            from web import _kia_uvo_transfer_enabled

            assert _kia_uvo_transfer_enabled() is True

    def test_returns_false_when_config_none(self):
        """_kia_uvo_transfer_enabled returns False when _kia_uvo_config returns None.

        Validates: Requirements 4.3
        """
        with patch("web._kia_uvo_config", return_value=None):
            from web import _kia_uvo_transfer_enabled

            assert _kia_uvo_transfer_enabled() is False


class TestKiaUvoIntegrationWithAutoStartLogin:
    """Tests for kia_uvo transfer integration in _auto_start_login().

    Since _auto_start_login is complex, we mock the login/token generation
    to succeed and verify the kia_uvo transfer integration behavior.

    Validates: Requirements 4.3, 4.4
    """

    def _run_auto_start_login_with_mocks(
        self,
        kia_uvo_enabled=True,
        kia_uvo_side_effect=None,
        evcc_configured=True,
    ):
        """Run _auto_start_login with all dependencies mocked for a successful login.

        Returns a dict with the mock objects for verification.
        """
        import web

        mock_kia_uvo_transfer = MagicMock(side_effect=kia_uvo_side_effect)
        mock_evcc_transfer = MagicMock()
        mock_schedule_reset = MagicMock()

        vehicles_config = [
            {"brand": "eu_kia", "username": "user@test.com", "password": "pass123"}
        ]

        # Set up env vars
        env_vars = {}
        if evcc_configured:
            env_vars["EVCC_URL"] = "http://evcc:7070"
            env_vars["EVCC_PASSWORD"] = "pw"

        # We need to patch many things to get _auto_start_login to reach
        # the kia_uvo transfer code path
        with patch.object(web, "_get_vehicles_config", return_value=vehicles_config), \
             patch.object(web, "_check_token_expiry", return_value=5), \
             patch.object(web, "_headless_login_eu_with_retry", return_value={"ok": True}), \
             patch.object(web, "_send_webhook", MagicMock()), \
             patch.object(web, "_send_ha_notification", MagicMock()), \
             patch.object(web, "update_ha_sensor", MagicMock()), \
             patch.object(web, "_kia_uvo_transfer_enabled", return_value=kia_uvo_enabled), \
             patch.object(web, "_auto_kia_uvo_transfer", mock_kia_uvo_transfer), \
             patch.object(web, "_auto_evcc_transfer", mock_evcc_transfer), \
             patch.object(web, "_schedule_auto_reset", mock_schedule_reset), \
             patch("time.sleep", MagicMock()), \
             patch.dict(os.environ, env_vars, clear=False):
            # Reset state for the test
            web.state["status"] = "idle"
            web.state["log"] = []
            web.state["vehicles"] = []
            web.state["refresh_token"] = "test_refresh_token"
            web.state["access_token"] = "test_access_token"

            # Remove _TEMP_VEHICLES if present
            os.environ.pop("_TEMP_VEHICLES", None)

            web._auto_start_login(force=True)

        return {
            "mock_kia_uvo_transfer": mock_kia_uvo_transfer,
            "mock_evcc_transfer": mock_evcc_transfer,
            "mock_schedule_reset": mock_schedule_reset,
        }

    def test_kia_uvo_transfer_called_after_successful_generation(self):
        """kia_uvo transfer is called with vehicles list after token generation succeeds.

        Validates: Requirements 4.3
        """
        result = self._run_auto_start_login_with_mocks(kia_uvo_enabled=True)

        # Verify _auto_kia_uvo_transfer was called
        result["mock_kia_uvo_transfer"].assert_called_once()
        # Verify it was called with the vehicles list
        call_args = result["mock_kia_uvo_transfer"].call_args[0]
        assert isinstance(call_args[0], list)
        assert len(call_args[0]) == 1
        assert call_args[0][0]["username"] == "user@test.com"

    def test_kia_uvo_failure_does_not_block_evcc(self):
        """kia_uvo transfer failure does not prevent evcc transfer from completing.

        The evcc transfer runs BEFORE kia_uvo in the code, so evcc always
        completes regardless of kia_uvo outcome. This test verifies the
        exception from kia_uvo is caught and doesn't propagate.

        Validates: Requirements 4.4
        """
        # kia_uvo raises an exception
        result = self._run_auto_start_login_with_mocks(
            kia_uvo_enabled=True,
            kia_uvo_side_effect=RuntimeError("kia_uvo exploded"),
        )

        # evcc transfer was still called (runs before kia_uvo)
        result["mock_evcc_transfer"].assert_called_once()
        # The function completed without raising (exception was caught)
        # If it raised, we'd never reach this assertion

    def test_both_transfers_execute_independently(self):
        """Both evcc and kia_uvo transfers are called when both are configured.

        Validates: Requirements 4.3, 4.4
        """
        result = self._run_auto_start_login_with_mocks(
            kia_uvo_enabled=True,
            evcc_configured=True,
        )

        # Both transfers should have been called
        result["mock_evcc_transfer"].assert_called_once()
        result["mock_kia_uvo_transfer"].assert_called_once()

    def test_kia_uvo_not_called_when_disabled(self):
        """kia_uvo transfer is NOT called when _kia_uvo_transfer_enabled returns False.

        Validates: Requirements 4.3
        """
        result = self._run_auto_start_login_with_mocks(kia_uvo_enabled=False)

        # kia_uvo transfer should NOT have been called
        result["mock_kia_uvo_transfer"].assert_not_called()

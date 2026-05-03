"""Unit tests for HA kia_uvo Token Transfer module.

Tests configuration parsing, entry detection, entry-vehicle matching,
reconfigure flow, and the orchestrator function.

Validates: Requirements 1.1-1.6, 2.1-2.4, 3.1-3.5, 5.1-5.5
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

# Add parent directory to path so we can import kia_uvo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kia_uvo import (
    _auto_kia_uvo_transfer,
    _detect_kia_uvo_entries,
    _kia_uvo_config,
    _match_entries_to_vehicles,
    _reconfigure_kia_uvo_entry,
)


# =============================================================================
# TestKiaUvoConfig - Test _kia_uvo_config() function
# =============================================================================


class TestKiaUvoConfig:
    """Test _kia_uvo_config() function.

    Validates: Requirements 1.1-1.6
    """

    def test_returns_none_when_ha_url_missing(self, clean_env, monkeypatch):
        """Returns None when HA_URL is not set but HA_TOKEN is.

        Validates: Requirements 1.6
        """
        monkeypatch.setenv("HA_TOKEN", "some_token")
        result = _kia_uvo_config()
        assert result is None

    def test_returns_none_when_ha_token_missing(self, clean_env, monkeypatch):
        """Returns None when HA_TOKEN is not set but HA_URL is.

        Validates: Requirements 1.6
        """
        monkeypatch.setenv("HA_URL", "http://ha.local:8123")
        result = _kia_uvo_config()
        assert result is None

    def test_returns_none_when_both_missing(self, clean_env):
        """Returns None when both HA_URL and HA_TOKEN are missing.

        Validates: Requirements 1.6
        """
        result = _kia_uvo_config()
        assert result is None

    def test_returns_none_when_transfer_false(self, mock_ha_env, monkeypatch):
        """Returns None when HA_KIA_UVO_TRANSFER is explicitly 'false'.

        Validates: Requirements 1.4
        """
        monkeypatch.setenv("HA_KIA_UVO_TRANSFER", "false")
        result = _kia_uvo_config()
        assert result is None

    def test_returns_config_when_transfer_true(self, mock_ha_env):
        """Returns config dict when HA_KIA_UVO_TRANSFER is 'true'.

        Validates: Requirements 1.3
        """
        result = _kia_uvo_config()
        assert result is not None
        assert result["ha_url"] == "http://homeassistant.local:8123"
        assert result["ha_token"] == "test_long_lived_token"
        assert result["enabled"] is True

    def test_auto_detect_mode_returns_config(self, clean_env, monkeypatch):
        """Returns config when HA_KIA_UVO_TRANSFER is unset (auto-detect mode).

        Validates: Requirements 1.5
        """
        monkeypatch.setenv("HA_URL", "http://ha.local:8123")
        monkeypatch.setenv("HA_TOKEN", "my_token")
        result = _kia_uvo_config()
        assert result is not None
        assert result["ha_url"] == "http://ha.local:8123"
        assert result["ha_token"] == "my_token"
        assert result["enabled"] is True

    def test_strips_trailing_slash_from_url(self, clean_env, monkeypatch):
        """Strips trailing slash from HA_URL.

        Validates: Requirements 1.1
        """
        monkeypatch.setenv("HA_URL", "http://ha.local:8123/")
        monkeypatch.setenv("HA_TOKEN", "my_token")
        monkeypatch.setenv("HA_KIA_UVO_TRANSFER", "true")
        result = _kia_uvo_config()
        assert result is not None
        assert result["ha_url"] == "http://ha.local:8123"

    def test_case_insensitive_true(self, clean_env, monkeypatch):
        """HA_KIA_UVO_TRANSFER='True' (mixed case) is treated as enabled.

        Validates: Requirements 1.3
        """
        monkeypatch.setenv("HA_URL", "http://ha.local:8123")
        monkeypatch.setenv("HA_TOKEN", "my_token")
        monkeypatch.setenv("HA_KIA_UVO_TRANSFER", "True")
        result = _kia_uvo_config()
        assert result is not None
        assert result["enabled"] is True

    def test_case_insensitive_false(self, clean_env, monkeypatch):
        """HA_KIA_UVO_TRANSFER='False' (mixed case) is treated as disabled.

        Validates: Requirements 1.4
        """
        monkeypatch.setenv("HA_URL", "http://ha.local:8123")
        monkeypatch.setenv("HA_TOKEN", "my_token")
        monkeypatch.setenv("HA_KIA_UVO_TRANSFER", "False")
        result = _kia_uvo_config()
        assert result is None


# =============================================================================
# TestDetectKiaUvoEntries - Test _detect_kia_uvo_entries() function
# =============================================================================


class TestDetectKiaUvoEntries:
    """Test _detect_kia_uvo_entries() function.

    Validates: Requirements 2.1-2.4
    """

    def test_returns_entries_on_success(self, sample_config_entries):
        """Returns list of config entries on successful API response.

        Validates: Requirements 2.2
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_config_entries
        mock_response.raise_for_status = MagicMock()

        with patch("kia_uvo.req_lib.get", return_value=mock_response):
            result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")

        assert result == sample_config_entries
        assert len(result) == 2

    def test_returns_empty_list_on_empty_response(self):
        """Returns empty list when HA API returns no entries.

        Validates: Requirements 2.3
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("kia_uvo.req_lib.get", return_value=mock_response):
            result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")

        assert result == []

    def test_returns_empty_list_on_http_401(self):
        """Returns empty list on HTTP 401 Unauthorized.

        Validates: Requirements 2.4
        """
        mock_response = MagicMock()
        mock_response.status_code = 401
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        with patch("kia_uvo.req_lib.get", return_value=mock_response):
            result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")

        assert result == []

    def test_returns_empty_list_on_http_500(self):
        """Returns empty list on HTTP 500 Internal Server Error.

        Validates: Requirements 2.4
        """
        mock_response = MagicMock()
        mock_response.status_code = 500
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        with patch("kia_uvo.req_lib.get", return_value=mock_response):
            result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")

        assert result == []

    def test_returns_empty_list_on_connection_error(self):
        """Returns empty list when HA is unreachable.

        Validates: Requirements 5.1
        """
        with patch(
            "kia_uvo.req_lib.get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")

        assert result == []

    def test_returns_empty_list_on_timeout(self):
        """Returns empty list on connection timeout.

        Validates: Requirements 5.1
        """
        with patch(
            "kia_uvo.req_lib.get",
            side_effect=requests.exceptions.Timeout("Connection timed out"),
        ):
            result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")

        assert result == []

    def test_uses_correct_url_and_headers(self):
        """Sends request to correct URL with Bearer token header.

        Validates: Requirements 2.1
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("kia_uvo.req_lib.get", return_value=mock_response) as mock_get:
            _detect_kia_uvo_entries("http://ha.local:8123", "my-secret-token")

        mock_get.assert_called_once_with(
            "http://ha.local:8123/api/config/config_entries/entry?domain=kia_uvo",
            headers={"Authorization": "Bearer my-secret-token"},
            timeout=(10, 30),
            verify=False,
        )


# =============================================================================
# TestMatchEntriesToVehicles - Test _match_entries_to_vehicles() function
# =============================================================================


class TestMatchEntriesToVehicles:
    """Test _match_entries_to_vehicles() function.

    Validates: Requirements 3.5
    """

    def test_matches_by_username(self, sample_config_entries, sample_vehicles):
        """Matches entries to vehicles by username.

        Validates: Requirements 3.5
        """
        matched = _match_entries_to_vehicles(sample_config_entries, sample_vehicles)
        assert len(matched) == 2
        # First match
        assert matched[0][0]["entry_id"] == "abc123def456"
        assert matched[0][1]["username"] == "user@example.com"
        # Second match
        assert matched[1][0]["entry_id"] == "xyz789ghi012"
        assert matched[1][1]["username"] == "other@example.com"

    def test_no_matches_when_usernames_differ(self):
        """Returns empty list when no usernames match.

        Validates: Requirements 3.5
        """
        entries = [
            {"entry_id": "e1", "data": {"username": "alice@example.com"}},
        ]
        vehicles = [
            {"username": "bob@example.com", "password": "pass"},
        ]
        matched = _match_entries_to_vehicles(entries, vehicles)
        assert matched == []

    def test_partial_matches(self):
        """Returns only matched pairs when some entries don't match.

        Validates: Requirements 3.5
        """
        entries = [
            {"entry_id": "e1", "data": {"username": "alice@example.com"}},
            {"entry_id": "e2", "data": {"username": "bob@example.com"}},
        ]
        vehicles = [
            {"username": "alice@example.com", "password": "pass"},
        ]
        matched = _match_entries_to_vehicles(entries, vehicles)
        assert len(matched) == 1
        assert matched[0][0]["entry_id"] == "e1"
        assert matched[0][1]["username"] == "alice@example.com"

    def test_empty_entries(self, sample_vehicles):
        """Returns empty list when entries list is empty.

        Validates: Requirements 3.5
        """
        matched = _match_entries_to_vehicles([], sample_vehicles)
        assert matched == []

    def test_empty_vehicles(self, sample_config_entries):
        """Returns empty list when vehicles list is empty.

        Validates: Requirements 3.5
        """
        matched = _match_entries_to_vehicles(sample_config_entries, [])
        assert matched == []

    def test_handles_entry_without_data_username(self):
        """Gracefully skips entries that don't have data.username.

        Validates: Requirements 3.5
        """
        entries = [
            {"entry_id": "e1", "data": {"region": 2}},  # no username
            {"entry_id": "e2", "data": {"username": "user@example.com"}},
        ]
        vehicles = [
            {"username": "user@example.com", "password": "pass"},
        ]
        matched = _match_entries_to_vehicles(entries, vehicles)
        assert len(matched) == 1
        assert matched[0][0]["entry_id"] == "e2"

    def test_handles_entry_with_none_data(self):
        """Gracefully skips entries where data is None.

        Validates: Requirements 3.5
        """
        entries = [
            {"entry_id": "e1", "data": None},
            {"entry_id": "e2", "data": {"username": "user@example.com"}},
        ]
        vehicles = [
            {"username": "user@example.com", "password": "pass"},
        ]
        matched = _match_entries_to_vehicles(entries, vehicles)
        assert len(matched) == 1
        assert matched[0][0]["entry_id"] == "e2"


# =============================================================================
# TestReconfigureKiaUvoEntry - Test _reconfigure_kia_uvo_entry() function
# =============================================================================


class TestReconfigureKiaUvoEntry:
    """Test _reconfigure_kia_uvo_entry() function.

    Validates: Requirements 3.1-3.4, 5.4
    """

    def _make_step_response(self, flow_id="flow_test_123"):
        """Create a successful step response mock."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"flow_id": flow_id, "type": "form"}
        return mock_resp

    def test_success_path(self, sample_flow_responses):
        """Returns True when all 4 steps complete successfully.

        Validates: Requirements 3.1, 3.2, 3.3
        """
        responses = []
        for step_key in ["step1", "step2", "step3", "step4"]:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = sample_flow_responses[step_key]
            responses.append(mock_resp)

        with patch("kia_uvo.req_lib.post", side_effect=responses):
            result = _reconfigure_kia_uvo_entry(
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                entry_id="abc123",
                username="user@example.com",
                password="pass123",
                pin="1234",
                region=2,
                brand=1,
            )

        assert result is True

    def test_returns_false_on_step1_http_error(self):
        """Returns False when step 1 (initiate flow) returns HTTP error.

        Validates: Requirements 3.4
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        http_error = requests.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_error

        with patch("kia_uvo.req_lib.post", return_value=mock_resp):
            result = _reconfigure_kia_uvo_entry(
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                entry_id="abc123",
                username="user@example.com",
                password="pass123",
                pin="1234",
            )

        assert result is False

    def test_returns_false_on_step2_http_error(self, sample_flow_responses):
        """Returns False when step 2 (reauth choice) returns HTTP error.

        Validates: Requirements 3.4
        """
        step1_resp = MagicMock()
        step1_resp.status_code = 200
        step1_resp.raise_for_status = MagicMock()
        step1_resp.json.return_value = sample_flow_responses["step1"]

        step2_resp = MagicMock()
        step2_resp.status_code = 400
        http_error = requests.exceptions.HTTPError(response=step2_resp)
        step2_resp.raise_for_status.side_effect = http_error

        with patch("kia_uvo.req_lib.post", side_effect=[step1_resp, step2_resp]):
            result = _reconfigure_kia_uvo_entry(
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                entry_id="abc123",
                username="user@example.com",
                password="pass123",
                pin="1234",
            )

        assert result is False

    def test_returns_false_on_step3_http_error(self, sample_flow_responses):
        """Returns False when step 3 (region/brand) returns HTTP error.

        Validates: Requirements 3.4
        """
        step1_resp = MagicMock()
        step1_resp.status_code = 200
        step1_resp.raise_for_status = MagicMock()
        step1_resp.json.return_value = sample_flow_responses["step1"]

        step2_resp = MagicMock()
        step2_resp.status_code = 200
        step2_resp.raise_for_status = MagicMock()
        step2_resp.json.return_value = sample_flow_responses["step2"]

        step3_resp = MagicMock()
        step3_resp.status_code = 500
        http_error = requests.exceptions.HTTPError(response=step3_resp)
        step3_resp.raise_for_status.side_effect = http_error

        with patch("kia_uvo.req_lib.post", side_effect=[step1_resp, step2_resp, step3_resp]):
            result = _reconfigure_kia_uvo_entry(
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                entry_id="abc123",
                username="user@example.com",
                password="pass123",
                pin="1234",
            )

        assert result is False

    def test_returns_false_on_step4_http_error(self, sample_flow_responses):
        """Returns False when step 4 (credentials) returns HTTP error.

        Validates: Requirements 3.4
        """
        step1_resp = MagicMock()
        step1_resp.status_code = 200
        step1_resp.raise_for_status = MagicMock()
        step1_resp.json.return_value = sample_flow_responses["step1"]

        step2_resp = MagicMock()
        step2_resp.status_code = 200
        step2_resp.raise_for_status = MagicMock()
        step2_resp.json.return_value = sample_flow_responses["step2"]

        step3_resp = MagicMock()
        step3_resp.status_code = 200
        step3_resp.raise_for_status = MagicMock()
        step3_resp.json.return_value = sample_flow_responses["step3"]

        step4_resp = MagicMock()
        step4_resp.status_code = 500
        http_error = requests.exceptions.HTTPError(response=step4_resp)
        step4_resp.raise_for_status.side_effect = http_error

        with patch(
            "kia_uvo.req_lib.post",
            side_effect=[step1_resp, step2_resp, step3_resp, step4_resp],
        ):
            result = _reconfigure_kia_uvo_entry(
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                entry_id="abc123",
                username="user@example.com",
                password="pass123",
                pin="1234",
            )

        assert result is False

    def test_returns_false_on_missing_flow_id(self):
        """Returns False when step 1 response has no flow_id.

        Validates: Requirements 5.3
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"type": "form", "step_id": "init"}  # no flow_id

        with patch("kia_uvo.req_lib.post", return_value=mock_resp):
            result = _reconfigure_kia_uvo_entry(
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                entry_id="abc123",
                username="user@example.com",
                password="pass123",
                pin="1234",
            )

        assert result is False

    def test_returns_false_on_malformed_json(self):
        """Returns False when step 1 response is malformed JSON.

        Validates: Requirements 5.3
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = ValueError("No JSON object could be decoded")

        with patch("kia_uvo.req_lib.post", return_value=mock_resp):
            result = _reconfigure_kia_uvo_entry(
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                entry_id="abc123",
                username="user@example.com",
                password="pass123",
                pin="1234",
            )

        assert result is False

    def test_returns_false_on_timeout(self):
        """Returns False on request timeout.

        Validates: Requirements 5.4
        """
        with patch(
            "kia_uvo.req_lib.post",
            side_effect=requests.exceptions.Timeout("Connection timed out"),
        ):
            result = _reconfigure_kia_uvo_entry(
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                entry_id="abc123",
                username="user@example.com",
                password="pass123",
                pin="1234",
            )

        assert result is False

    def test_returns_false_on_connection_error(self):
        """Returns False on connection error.

        Validates: Requirements 5.1
        """
        with patch(
            "kia_uvo.req_lib.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            result = _reconfigure_kia_uvo_entry(
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                entry_id="abc123",
                username="user@example.com",
                password="pass123",
                pin="1234",
            )

        assert result is False


# =============================================================================
# TestAutoKiaUvoTransfer - Test _auto_kia_uvo_transfer() orchestrator
# =============================================================================


class TestAutoKiaUvoTransfer:
    """Test _auto_kia_uvo_transfer() orchestrator function.

    Validates: Requirements 5.1-5.5
    """

    def test_skips_when_config_none(self):
        """Skips transfer when _kia_uvo_config returns None.

        Validates: Requirements 1.6
        """
        with patch("kia_uvo._kia_uvo_config", return_value=None):
            # Should not raise
            _auto_kia_uvo_transfer([{"username": "user@example.com", "password": "pass"}])

    def test_skips_when_no_entries_found(self, mock_ha_env):
        """Skips transfer when no kia_uvo entries are detected.

        Validates: Requirements 2.3
        """
        with patch("kia_uvo._detect_kia_uvo_entries", return_value=[]):
            _auto_kia_uvo_transfer([{"username": "user@example.com", "password": "pass"}])

    def test_skips_when_no_matches(self, mock_ha_env, sample_config_entries):
        """Skips transfer when no entries match any vehicle.

        Validates: Requirements 3.5
        """
        vehicles = [{"username": "nomatch@example.com", "password": "pass"}]

        with patch("kia_uvo._detect_kia_uvo_entries", return_value=sample_config_entries):
            _auto_kia_uvo_transfer(vehicles)

    def test_calls_reconfigure_for_each_match(
        self, mock_ha_env, sample_config_entries, sample_vehicles
    ):
        """Calls _reconfigure_kia_uvo_entry for each matched entry/vehicle pair.

        Validates: Requirements 3.1, 3.5
        """
        with patch("kia_uvo._detect_kia_uvo_entries", return_value=sample_config_entries), \
             patch("kia_uvo._reconfigure_kia_uvo_entry", return_value=True) as mock_reconf:
            _auto_kia_uvo_transfer(sample_vehicles)

        # Should be called twice (one for each matched pair)
        assert mock_reconf.call_count == 2

        # Verify first call args
        first_call = mock_reconf.call_args_list[0]
        assert first_call.kwargs["entry_id"] == "abc123def456"
        assert first_call.kwargs["username"] == "user@example.com"
        assert first_call.kwargs["password"] == "pass123"
        assert first_call.kwargs["pin"] == "1234"  # from vehicle config

        # Verify second call args
        second_call = mock_reconf.call_args_list[1]
        assert second_call.kwargs["entry_id"] == "xyz789ghi012"
        assert second_call.kwargs["username"] == "other@example.com"
        assert second_call.kwargs["password"] == "pass456"

    def test_uses_vehicle_pin_over_env_pin(self, mock_ha_env):
        """Uses vehicle-specific pin when available, not env var fallback.

        Validates: Requirements 5.5
        """
        entries = [{"entry_id": "e1", "data": {"username": "user@example.com", "region": 2, "brand": 1}}]
        vehicles = [{"username": "user@example.com", "password": "pass", "pin": "9999"}]

        with patch("kia_uvo._detect_kia_uvo_entries", return_value=entries), \
             patch("kia_uvo._reconfigure_kia_uvo_entry", return_value=True) as mock_reconf:
            _auto_kia_uvo_transfer(vehicles)

        # Vehicle pin "9999" should be used, not env var "0000"
        call_kwargs = mock_reconf.call_args.kwargs
        assert call_kwargs["pin"] == "9999"

    def test_falls_back_to_env_pin(self, mock_ha_env):
        """Falls back to HA_KIA_UVO_PIN env var when vehicle has no pin.

        Validates: Requirements 5.5
        """
        entries = [{"entry_id": "e1", "data": {"username": "user@example.com", "region": 2, "brand": 1}}]
        vehicles = [{"username": "user@example.com", "password": "pass"}]  # no pin field

        with patch("kia_uvo._detect_kia_uvo_entries", return_value=entries), \
             patch("kia_uvo._reconfigure_kia_uvo_entry", return_value=True) as mock_reconf:
            _auto_kia_uvo_transfer(vehicles)

        # Should use env var "0000" (set by mock_ha_env fixture)
        call_kwargs = mock_reconf.call_args.kwargs
        assert call_kwargs["pin"] == "0000"

    def test_never_raises_on_unexpected_error(self):
        """Never raises exceptions even on unexpected errors.

        Validates: Requirements 5.3
        """
        with patch("kia_uvo._kia_uvo_config", side_effect=RuntimeError("Unexpected!")):
            # Should not raise
            _auto_kia_uvo_transfer([{"username": "user@example.com", "password": "pass"}])

"""Property-based tests for HA kia_uvo detection and matching logic.

Feature: ha-kia-uvo-token-transfer
Validates: Requirements 2.2, 3.5
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

# Add parent directory to path so we can import kia_uvo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kia_uvo import _detect_kia_uvo_entries, _match_entries_to_vehicles


# --- Strategies ---

# Strategy for generating valid email-like usernames
username_st = st.emails()

# Strategy for generating entry_id strings (non-empty alphanumeric)
entry_id_st = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
    min_size=1,
    max_size=32,
)

# Strategy for a single config entry dict
config_entry_st = st.fixed_dictionaries(
    {
        "entry_id": entry_id_st,
        "domain": st.just("kia_uvo"),
        "data": st.fixed_dictionaries(
            {
                "username": username_st,
                "region": st.integers(min_value=1, max_value=5),
                "brand": st.integers(min_value=1, max_value=3),
            }
        ),
    }
)

# Strategy for a list of config entries
config_entries_st = st.lists(config_entry_st, min_size=0, max_size=10)

# Strategy for a single vehicle dict
vehicle_st = st.fixed_dictionaries(
    {
        "username": username_st,
        "password": st.text(min_size=1, max_size=20),
    }
)

# Strategy for a list of vehicles
vehicles_st = st.lists(vehicle_st, min_size=0, max_size=10)


# --- Property 1: Entry ID extraction completeness ---


class TestEntryIdExtractionCompleteness:
    """Property 1: Entry ID extraction completeness.

    Feature: ha-kia-uvo-token-transfer, Property 1: Entry ID extraction completeness

    For any list of config entry objects returned by the HA API (each containing
    an `entry_id` field), the detection function SHALL extract and return all
    `entry_id` values without loss or duplication.

    **Validates: Requirements 2.2**
    """

    @given(entries=config_entries_st)
    @settings(max_examples=100)
    def test_all_entry_ids_extracted_without_loss(self, entries: list[dict]):
        """Detection returns all entries from the API response without loss.

        **Validates: Requirements 2.2**
        """
        # Mock the HTTP response to return our generated entries
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = entries
        mock_response.raise_for_status = MagicMock()

        with patch("kia_uvo.req_lib.get", return_value=mock_response):
            result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")

        # All entry_ids from input should be present in result
        input_entry_ids = [e["entry_id"] for e in entries]
        result_entry_ids = [e["entry_id"] for e in result]

        assert len(result_entry_ids) == len(input_entry_ids), (
            f"Expected {len(input_entry_ids)} entries, got {len(result_entry_ids)}"
        )
        assert set(result_entry_ids) == set(input_entry_ids), (
            "Not all entry_ids were preserved in the result"
        )

    @given(entries=config_entries_st)
    @settings(max_examples=100)
    def test_no_duplicate_entries_in_result(self, entries: list[dict]):
        """Detection does not introduce duplicate entries.

        **Validates: Requirements 2.2**
        """
        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = entries
        mock_response.raise_for_status = MagicMock()

        with patch("kia_uvo.req_lib.get", return_value=mock_response):
            result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")

        # Result should have same length as input (no duplicates introduced)
        assert len(result) == len(entries), (
            f"Result length {len(result)} differs from input length {len(entries)}: "
            "detection introduced or removed entries"
        )


# --- Property 4: Username-based entry matching ---


class TestUsernameBasedEntryMatching:
    """Property 4: Username-based entry matching.

    Feature: ha-kia-uvo-token-transfer, Property 4: Username-based entry matching

    For any set of config entries (each with a `data.username` field) and any set
    of vehicle credentials (each with a `username` field), the matching function
    SHALL pair entries to vehicles where usernames are equal, and SHALL not produce
    false matches.

    **Validates: Requirements 3.5**
    """

    @given(entries=config_entries_st, vehicles=vehicles_st)
    @settings(max_examples=100)
    def test_all_matched_pairs_have_equal_usernames(
        self, entries: list[dict], vehicles: list[dict]
    ):
        """Every matched pair has equal usernames (no false matches).

        **Validates: Requirements 3.5**
        """
        matched = _match_entries_to_vehicles(entries, vehicles)

        for entry, vehicle in matched:
            assert entry["data"]["username"] == vehicle["username"], (
                f"False match: entry username '{entry['data']['username']}' "
                f"!= vehicle username '{vehicle['username']}'"
            )

    @given(entries=config_entries_st, vehicles=vehicles_st)
    @settings(max_examples=100)
    def test_matchable_entries_are_matched(
        self, entries: list[dict], vehicles: list[dict]
    ):
        """If an entry's username exists in vehicles, it should be matched.

        **Validates: Requirements 3.5**
        """
        matched = _match_entries_to_vehicles(entries, vehicles)
        matched_entry_ids = {e["entry_id"] for e, _ in matched}

        vehicle_usernames = {v["username"] for v in vehicles}

        for entry in entries:
            entry_username = entry.get("data", {}).get("username")
            if entry_username and entry_username in vehicle_usernames:
                assert entry["entry_id"] in matched_entry_ids, (
                    f"Entry '{entry['entry_id']}' with username '{entry_username}' "
                    f"should have been matched but wasn't"
                )

    @given(entries=config_entries_st, vehicles=vehicles_st)
    @settings(max_examples=100)
    def test_no_false_matches_produced(
        self, entries: list[dict], vehicles: list[dict]
    ):
        """No matched pair has mismatched usernames.

        **Validates: Requirements 3.5**
        """
        matched = _match_entries_to_vehicles(entries, vehicles)

        for entry, vehicle in matched:
            entry_username = entry["data"]["username"]
            vehicle_username = vehicle["username"]
            assert entry_username == vehicle_username, (
                f"False match detected: entry='{entry_username}', "
                f"vehicle='{vehicle_username}'"
            )


# --- Property 3: Reconfigure flow resilience ---

import requests as req_lib_module

from kia_uvo import _reconfigure_kia_uvo_entry

# Strategy for HTTP error status codes (4xx and 5xx)
http_error_status_st = st.one_of(
    st.integers(min_value=400, max_value=499),
    st.integers(min_value=500, max_value=599),
)

# Strategy for the step number where the error occurs (1-4)
error_step_st = st.integers(min_value=1, max_value=4)

# Strategy for error types
error_type_st = st.sampled_from([
    "http_error",
    "timeout",
    "connection_error",
    "malformed_json",
    "missing_flow_id",
])


def _make_valid_step_response(step_num: int) -> MagicMock:
    """Create a valid mock response for a given step number."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "flow_id": f"flow_abc_{step_num}",
        "type": "form",
        "step_id": f"step_{step_num}",
    }
    return mock_resp


def _make_error_response(error_type: str, status_code: int) -> MagicMock:
    """Create a mock response or side effect for a given error type."""
    if error_type == "http_error":
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        http_error = req_lib_module.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_error
        return mock_resp
    elif error_type == "timeout":
        # Return a side_effect that raises Timeout
        return "timeout"
    elif error_type == "connection_error":
        # Return a side_effect that raises ConnectionError
        return "connection_error"
    elif error_type == "malformed_json":
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = ValueError("No JSON object could be decoded")
        return mock_resp
    elif error_type == "missing_flow_id":
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"type": "form", "step_id": "some_step"}
        return mock_resp
    else:
        raise ValueError(f"Unknown error type: {error_type}")


class TestReconfigureFlowResilience:
    """Property 3: Reconfigure flow resilience.

    Feature: ha-kia-uvo-token-transfer, Property 3: Reconfigure flow resilience

    For any error condition during the reconfigure flow (HTTP errors, malformed JSON
    responses, missing fields, timeouts), the system SHALL log the error and continue
    processing remaining config entries without crashing.

    **Validates: Requirements 3.4, 5.3**
    """

    @given(
        error_step=error_step_st,
        error_type=error_type_st,
        status_code=http_error_status_st,
    )
    @settings(max_examples=100)
    def test_reconfigure_returns_false_on_any_error(
        self, error_step: int, error_type: str, status_code: int
    ):
        """For any error at any step, _reconfigure_kia_uvo_entry returns False without raising.

        **Validates: Requirements 3.4, 5.3**
        """
        # Build the list of side effects for req_lib.post calls
        # Steps before error_step return valid responses
        # The step at error_step triggers the error
        side_effects = []

        for step in range(1, error_step):
            side_effects.append(_make_valid_step_response(step))

        # Now add the error for the target step
        error_resp = _make_error_response(error_type, status_code)
        if error_resp == "timeout":
            side_effects.append(req_lib_module.exceptions.Timeout("Connection timed out"))
        elif error_resp == "connection_error":
            side_effects.append(req_lib_module.exceptions.ConnectionError("Connection refused"))
        else:
            side_effects.append(error_resp)

        def post_side_effect(*args, **kwargs):
            """Pop the next response/exception from the side_effects list."""
            if not side_effects:
                # Should not reach here, but return a valid response just in case
                return _make_valid_step_response(99)
            effect = side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return effect

        with patch("kia_uvo.req_lib.post", side_effect=post_side_effect):
            # This should NOT raise any exception
            result = _reconfigure_kia_uvo_entry(
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                entry_id="test_entry_123",
                username="user@example.com",
                password="password123",
                pin="1234",
                region=2,
                brand=1,
            )

        # Must return False (not True) on any error
        assert result is False, (
            f"Expected False for error_type={error_type} at step {error_step}, "
            f"but got {result}"
        )

    @given(
        error_step=error_step_st,
        error_type=error_type_st,
        status_code=http_error_status_st,
    )
    @settings(max_examples=100)
    def test_reconfigure_never_raises_on_error(
        self, error_step: int, error_type: str, status_code: int
    ):
        """For any error at any step, _reconfigure_kia_uvo_entry does NOT raise an exception.

        **Validates: Requirements 3.4, 5.3**
        """
        side_effects = []

        for step in range(1, error_step):
            side_effects.append(_make_valid_step_response(step))

        error_resp = _make_error_response(error_type, status_code)
        if error_resp == "timeout":
            side_effects.append(req_lib_module.exceptions.Timeout("Connection timed out"))
        elif error_resp == "connection_error":
            side_effects.append(req_lib_module.exceptions.ConnectionError("Connection refused"))
        else:
            side_effects.append(error_resp)

        def post_side_effect(*args, **kwargs):
            if not side_effects:
                return _make_valid_step_response(99)
            effect = side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return effect

        with patch("kia_uvo.req_lib.post", side_effect=post_side_effect):
            # The function must complete without raising
            try:
                _reconfigure_kia_uvo_entry(
                    ha_url="http://ha.local:8123",
                    ha_token="test-token",
                    entry_id="test_entry_456",
                    username="user@example.com",
                    password="password123",
                    pin="1234",
                    region=2,
                    brand=1,
                )
            except Exception as e:
                raise AssertionError(
                    f"_reconfigure_kia_uvo_entry raised {type(e).__name__}: {e} "
                    f"for error_type={error_type} at step {error_step}"
                )


# --- Property 2: HTTP error resilience during detection ---


class TestHttpErrorResilienceDuringDetection:
    """Property 2: HTTP error resilience during detection.

    Feature: ha-kia-uvo-token-transfer, Property 2: HTTP error resilience during detection

    For any HTTP error status code (4xx or 5xx) returned by the HA API during
    config entry detection, the system SHALL return an empty list and not raise
    an exception.

    **Validates: Requirements 2.4**
    """

    @given(status_code=http_error_status_st)
    @settings(max_examples=100)
    def test_http_error_returns_empty_list(self, status_code: int):
        """For any HTTP error status code, detection returns an empty list.

        **Validates: Requirements 2.4**
        """
        mock_response = MagicMock()
        mock_response.status_code = status_code
        http_error = req_lib_module.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        with patch("kia_uvo.req_lib.get", return_value=mock_response):
            result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")

        assert result == [], (
            f"Expected empty list for HTTP {status_code}, got {result}"
        )

    @given(status_code=http_error_status_st)
    @settings(max_examples=100)
    def test_http_error_does_not_raise(self, status_code: int):
        """For any HTTP error status code, detection does NOT raise an exception.

        **Validates: Requirements 2.4**
        """
        mock_response = MagicMock()
        mock_response.status_code = status_code
        http_error = req_lib_module.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        with patch("kia_uvo.req_lib.get", return_value=mock_response):
            try:
                _detect_kia_uvo_entries("http://ha.local:8123", "test-token")
            except Exception as e:
                raise AssertionError(
                    f"_detect_kia_uvo_entries raised {type(e).__name__}: {e} "
                    f"for HTTP status {status_code}"
                )

    @given(data=st.data())
    @settings(max_examples=100)
    def test_timeout_returns_empty_list_no_exception(self, data):
        """Connection timeouts return empty list without raising.

        **Validates: Requirements 2.4**
        """
        # Draw a status code just to vary the test inputs across iterations
        _ = data.draw(http_error_status_st)

        with patch(
            "kia_uvo.req_lib.get",
            side_effect=req_lib_module.exceptions.Timeout("Connection timed out"),
        ):
            try:
                result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")
            except Exception as e:
                raise AssertionError(
                    f"_detect_kia_uvo_entries raised {type(e).__name__}: {e} "
                    f"on Timeout"
                )

        assert result == [], f"Expected empty list on Timeout, got {result}"

    @given(data=st.data())
    @settings(max_examples=100)
    def test_connection_error_returns_empty_list_no_exception(self, data):
        """Connection errors return empty list without raising.

        **Validates: Requirements 2.4**
        """
        _ = data.draw(http_error_status_st)

        with patch(
            "kia_uvo.req_lib.get",
            side_effect=req_lib_module.exceptions.ConnectionError("Connection refused"),
        ):
            try:
                result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")
            except Exception as e:
                raise AssertionError(
                    f"_detect_kia_uvo_entries raised {type(e).__name__}: {e} "
                    f"on ConnectionError"
                )

        assert result == [], f"Expected empty list on ConnectionError, got {result}"

    @given(data=st.data())
    @settings(max_examples=100)
    def test_generic_exception_returns_empty_list_no_exception(self, data):
        """Generic exceptions return empty list without raising.

        **Validates: Requirements 2.4**
        """
        _ = data.draw(http_error_status_st)

        with patch(
            "kia_uvo.req_lib.get",
            side_effect=RuntimeError("Something unexpected happened"),
        ):
            try:
                result = _detect_kia_uvo_entries("http://ha.local:8123", "test-token")
            except Exception as e:
                raise AssertionError(
                    f"_detect_kia_uvo_entries raised {type(e).__name__}: {e} "
                    f"on generic exception"
                )

        assert result == [], f"Expected empty list on generic exception, got {result}"

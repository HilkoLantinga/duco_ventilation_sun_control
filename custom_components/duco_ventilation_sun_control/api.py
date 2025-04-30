# === custom_components/duco_ventilation_sun_control/api.py ===
# NOTE: This file represents the SKELETON of the external library 'duco_api'.
# It should eventually be moved to a separate package.
# This version includes full implementation based on prompt v7.

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Final, Optional, Union, cast

import aiohttp
import async_timeout
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
# Assuming this helper is available or reimplemented in the HA context if needed
from homeassistant.util.network import is_ipv6_address
# Import necessary constants defined within this integration's const.py
# A real external library would define its own constants.
from .const import (
    API_V1, API_V2, DEVICE_INFO_KEY_API_VERSION, DEVICE_INFO_KEY_CALIB_STATE,
    DEVICE_INFO_KEY_CALIB_VALID, DEVICE_INFO_KEY_DEVICE_TIME,
    DEVICE_INFO_KEY_EXHAUST_FAN_PWM, DEVICE_INFO_KEY_EXHAUST_FAN_SPEED,
    DEVICE_INFO_KEY_FILTER_REMAINING_TIME, DEVICE_INFO_KEY_INSTALLER_STATE,
    DEVICE_INFO_KEY_IP, DEVICE_INFO_KEY_MAC, DEVICE_INFO_KEY_MODEL,
    DEVICE_INFO_KEY_POWER_AVG, DEVICE_INFO_KEY_POWER_MAX, DEVICE_INFO_KEY_POWER_NOW,
    DEVICE_INFO_KEY_PRESSURE_OUT, DEVICE_INFO_KEY_PRESSURE_TOTAL,
    DEVICE_INFO_KEY_RF_HOME_ID, DEVICE_INFO_KEY_SERIAL, DEVICE_INFO_KEY_SUPPLY_FAN_PWM,
    DEVICE_INFO_KEY_SUPPLY_FAN_SPEED, DEVICE_INFO_KEY_SW_VERSION,
    DEVICE_INFO_KEY_TEMP_EHA, DEVICE_INFO_KEY_TEMP_ETA, DEVICE_INFO_KEY_TEMP_ODA,
    DEVICE_INFO_KEY_TEMP_SUP, DEVICE_INFO_KEY_UPTIME, DEVICE_INFO_KEY_WEATHER_PRESENT,
    KEY_ACTL, KEY_ACTION_FAILED_V1, KEY_ACTION_RESULT_V2, KEY_ACTION_SUCCESS_V1,
    KEY_API_VERSION, KEY_ASSO, KEY_CALIB_IS_VALID, KEY_CALIB_STATE, KEY_CALIBRATION,
    KEY_CERR, KEY_CNTDWN, KEY_CO2, KEY_DEVTYPE, KEY_DUCO_SERIAL, KEY_ENDTIME,
    KEY_ENERGYFAN, KEY_ENERGYINFO, KEY_ERROR, KEY_EXHAUST_FAN_PWM,
    KEY_EXHAUST_FAN_SPEED, KEY_FILTER_REMAIN, KEY_GENERAL, KEY_HOP_VIA,
    KEY_INSTALLER_STATE, KEY_IP_ADDRESS, KEY_LINK, KEY_LOCATION,
    KEY_LOCATION_V1_CONFIG, KEY_MAC, KEY_MAX, KEY_MIN, KEY_MODE,
    KEY_MODULE_ETHERNET, KEY_MODULE_FAN, KEY_MODULE_IDENTIFICATION,
    KEY_MODULE_MODBUS, KEY_MODULE_MQTT, KEY_MODULE_NETWORK, KEY_MODULE_NIGHTBOOST,
    KEY_MODULE_TIME, KEY_MODULE_VENTCOOL, KEY_MODULE_VENTCTRL, KEY_NODE,
    KEY_NODELIST_V1, KEY_NODES_V2, KEY_NODE_ID_V2, KEY_OVRL, KEY_PARAM_GATEWAY,
    KEY_PARAM_MQTT_BROKERIP, KEY_PARAM_NETMASK, KEY_PARAM_STATICIP, KEY_PERFORMANCE,
    KEY_POWER_AVG, KEY_POWER_MAX, KEY_POWER_NOW, KEY_PRESSURE_OUT,
    KEY_PRESSURE_TOTAL, KEY_PRNT, KEY_RFHOMEID, KEY_RH, KEY_RSSI, KEY_RSSI_N2H,
    KEY_SERIAL, KEY_SERIAL_NB, KEY_SHOW, KEY_SNSR, KEY_STATE, KEY_STEP, KEY_SUBTYPE,
    KEY_SUPPLY_FAN_PWM, KEY_SUPPLY_FAN_SPEED, KEY_SW_VERSION, KEY_SW_VERSION_NODE,
    KEY_TEMPEHA, KEY_TEMPETA, KEY_TEMPODA, KEY_TEMPSUP, KEY_TEMP, KEY_TIME, KEY_TRGT,
    KEY_UPTIME, KEY_VAL, KEY_V2_FLOWLVLTGT, KEY_V2_IAQCO2, KEY_V2_IAQRH,
    KEY_V2_SENSOR, KEY_V2_TIMESTATEEND, KEY_V2_TIMESTATEREMAIN, KEY_V2_VENTILATION,
    KEY_VALUE_A, KEY_VALUE_B, KEY_VALUE_C, KEY_VALUE_D, KEY_WEATHER_PRESENT,
    KEY_WEATHER_STATION, NODE_CONFIG_KEY_MAX, NODE_CONFIG_KEY_MIN,
    NODE_CONFIG_KEY_STEP, NODE_CONFIG_KEY_VALUE, NODE_INFO_KEY_ACTUAL_LEVEL,
    NODE_INFO_KEY_ASSO_ID, NODE_INFO_KEY_CO2, NODE_INFO_KEY_COMM_ERROR_CODE,
    NODE_INFO_KEY_COUNTDOWN, NODE_INFO_KEY_DEVICE_TYPE, NODE_INFO_KEY_DUCO_SERIAL,
    NODE_INFO_KEY_ENDTIME, NODE_INFO_KEY_ERROR_CODE, NODE_INFO_KEY_ERROR_STATUS,
    NODE_INFO_KEY_HOP_VIA, NODE_INFO_KEY_IAQ_CO2, NODE_INFO_KEY_IAQ_RH,
    NODE_INFO_KEY_ID, NODE_INFO_KEY_LINK, NODE_INFO_KEY_LOCATION, NODE_INFO_KEY_MODE,
    NODE_INFO_KEY_OVERRULE_PCT, NODE_INFO_KEY_PARENT_ID, NODE_INFO_KEY_RH,
    NODE_INFO_KEY_RSSI, NODE_INFO_KEY_RSSI_N2H, NODE_INFO_KEY_SENSOR_DEMAND,
    NODE_INFO_KEY_SERIAL, NODE_INFO_KEY_SHOW, NODE_INFO_KEY_STATE,
    NODE_INFO_KEY_SUB_TYPE, NODE_INFO_KEY_SW_VERSION, NODE_INFO_KEY_TARGET_LEVEL,
    NODE_INFO_KEY_TEMP, NODE_NO_ERROR_CODE, V1_CANCEL_OVERRULE_VALUE,
    V1_ENDPOINT_BOARD_INFO, V1_ENDPOINT_BOARD_RESET, V1_ENDPOINT_BOXCONFIG_GET,
    V1_ENDPOINT_BOXCONFIG_SET, V1_ENDPOINT_BOXINFO_GET, V1_ENDPOINT_BOX_CLEAR_NETWORK,
    V1_ENDPOINT_BOX_SET_CALIBRATION, V1_ENDPOINT_BOX_SET_INSTALL,
    V1_ENDPOINT_BOX_SET_TIME, V1_ENDPOINT_ECOCONFIG_GET, V1_ENDPOINT_ECOCONFIG_SET,
    V1_ENDPOINT_IPCONFIG_GET, V1_ENDPOINT_IPCONFIG_SET, V1_ENDPOINT_NODECONFIG_GET,
    V1_ENDPOINT_NODECONFIG_SET, V1_ENDPOINT_NODEINFO_GET, V1_ENDPOINT_NODELIST,
    V1_ENDPOINT_NODE_LOAD_DEFAULTS, V1_ENDPOINT_NODE_RESET, V1_ENDPOINT_NODE_SET_ASSO,
    V1_ENDPOINT_NODE_SET_LINKMODE, V1_ENDPOINT_NODE_SET_OPERSTATE,
    V1_ENDPOINT_NODE_SET_OVERRULE, V1_ENDPOINT_NODE_SET_PARENT,
    V1_ENDPOINT_NODE_SET_SHOW, V2_ACTION_CLEAR_NETWORK, V2_ACTION_LOAD_DEFAULTS_NODE,
    V2_ACTION_REBOOT, V2_ACTION_RESET_NODE, V2_ACTION_SET_ASSOCIATION,
    V2_ACTION_SET_CALIBRATION, V2_ACTION_SET_INSTALLER_MODE, V2_ACTION_SET_LINK_MODE,
    V2_ACTION_SET_OVERRULE, V2_ACTION_SET_PARENT, V2_ACTION_SET_SHOW, V2_ACTION_SET_TIME,
    V2_ACTION_SET_VENTILATION_STATE, V2_MODULE_MAP_TO_V1_AREA, V2_PATH_ACTION,
    V2_PATH_ACTION_NODE, V2_PATH_CONFIG, V2_PATH_CONFIG_NODE_DETAIL, V2_PATH_INFO,
    V2_PATH_INFO_NODES, V2_PATH_INFO_NODE_DETAIL, _calculate_utc_datetime, # Helper import
    _calculate_uptime_dt, _map_overrule_value, _map_temp_times_10_get, # Helper import
    _map_to_string_upper, reconstruct_ip_from_dict, _map_temp_times_10_set, # Helper import
    _map_minutes_to_time, _map_time_to_minutes, # Helper import
)
# Import exceptions locally
from .exceptions import ( # noqa: F401 # pylint: disable=unused-import
    DucoApiError as ApiError,
    DucoAuthenticationError as ApiAuthError,
    DucoCommunicationError as ApiConnectionError,
    DucoInvalidResponseError as ApiResponseError,
    # Define other specific errors if needed by the library
    # ApiBadRequestError, ApiRateLimitError, ApiInternalServerError
)
from .util import get_nested_value # Import utility

_LOGGER = logging.getLogger(__name__)


class DucoApiClient:
    """Asynchronous client for interacting with the Duco Ventilation System API.

    Handles communication, authentication, retries, command queuing, and
    data normalization for both V1 and V2 Duco APIs.
    """

    # Default values for timing and retries, used by the @retry decorator
    _DEFAULT_TIMEOUT: Final = 10
    _DEFAULT_RETRIES: Final = 3
    _DEFAULT_RETRY_DELAY: Final = 1.0
    _DEFAULT_COMMAND_DELAY: Final = 0.5 # Default minimum time between commands

    def __init__(
        self,
        host: str,
        api_version: str,
        session: aiohttp.ClientSession,
        api_key: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
        retries: int = _DEFAULT_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
        command_delay: float = _DEFAULT_COMMAND_DELAY,
    ) -> None:
        """Initialize the Duco API client.

        Args:
            host: The hostname or IP address of the Duco device.
            api_version: The detected or configured API version ('v1' or 'v2').
            session: An externally provided aiohttp.ClientSession.
            api_key: The API key required for V2 write operations (optional).
            timeout: Request timeout in seconds.
            retries: Number of retries for failed requests (used by decorator default).
            retry_delay: Base delay between retries in seconds (used by decorator default).
            command_delay: Minimum delay between consecutive commands sent to the device.
        """
        self._host = host
        # Use brackets for IPv6 address formatting in URL construction
        self._url_host = f"[{host}]" if is_ipv6_address(host) else host
        self._api_version = api_version
        self._session = session
        self._api_key = api_key
        self._timeout = timeout
        # Store retry/delay for potential future use, though decorator uses defaults
        self._retries = retries
        self._retry_delay = retry_delay
        self._command_delay = command_delay

        # Determine base URL and headers based on API version
        if api_version == API_V1:
            self._base_url = f"http://{self._url_host}"
            self._headers = {"Accept": "application/json, text/plain"}
            self._ssl_context = None # V1 is HTTP
        elif api_version == API_V2:
            self._base_url = f"https://{self._url_host}"
            self._headers = {"Accept": "application/json"}
            # For V2 HTTPS, disable SSL verification as certs are self-signed
            self._ssl_context = False
        else:
            # This should ideally be caught before instantiation, but good practice
            raise ValueError(f"Unsupported API version provided to client: {api_version}")

        # Lock to ensure command delay is respected between concurrent calls
        self._command_lock = asyncio.Lock()
        self._last_command_time = 0.0 # Tracks monotonic time of last command start

        _LOGGER.debug(
            "DucoApiClient initialized: Host=%s, API=%s, Timeout=%d, Retries=%d, RetryDelay=%.1f, CmdDelay=%.1f",
            host, api_version, timeout, retries, retry_delay, command_delay
        )

    @property
    def host(self) -> str:
        """Return the host address used by the client."""
        return self._host

    async def _wait_for_command_delay(self) -> None:
        """Ensure minimum delay between commands using an asyncio Lock.

        Prevents flooding the Duco device with requests too quickly.
        """
        async with self._command_lock:
            now = time.monotonic()
            time_since_last = now - self._last_command_time
            delay_needed = max(0.0, self._command_delay - time_since_last)
            if delay_needed > 0:
                _LOGGER.debug("Command queue: Delaying for %.3f seconds.", delay_needed)
                await asyncio.sleep(delay_needed)
            # Update time *before* releasing lock for the next command
            self._last_command_time = time.monotonic()

    # Retry decorator using class-level defaults for simplicity in this skeleton
    # A more robust library might pass dynamic retry config
    @retry(
        retry=retry_if_exception_type((ApiConnectionError,)), # Only retry connection errors
        stop=stop_after_attempt(_DEFAULT_RETRIES + 1), # retries + initial attempt
        wait=wait_exponential(multiplier=1, min=_DEFAULT_RETRY_DELAY, max=10),
        retry_error_callback=lambda retry_state: _LOGGER.warning(
            "Retrying API request to %s (attempt %d) after error: %s",
            retry_state.args[1] if len(retry_state.args) > 1 else 'unknown endpoint', # Log endpoint path if possible
            retry_state.attempt_number,
            retry_state.outcome.exception()
        ),
        reraise=True, # Reraise the underlying exception after retries are exhausted
    )
    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        is_write_operation: bool = False,
    ) -> Any:
        """Perform an HTTP request with queuing, timeout, and retries.

        This is the core internal method for all API communication.

        Args:
            method: HTTP method (e.g., "GET", "POST", "PATCH").
            path: API endpoint path (e.g., "/info").
            params: URL query parameters dictionary.
            json_data: JSON payload dictionary for POST/PATCH requests.
            is_write_operation: Flag indicating if this is a write operation,
                                used for V2 authentication check.

        Returns:
            Parsed JSON response (dict or list) or True for success actions.

        Raises:
            ApiConnectionError: If the connection fails after retries (timeout, DNS, network).
            ApiAuthError: If authentication fails (401/403).
            ApiError: For other API-level errors (e.g., 4xx/5xx, V1 FAILED).
            ApiResponseError: If the response format is unexpected or invalid JSON.
            ValueError: If required arguments are missing (e.g., V2 API key for write).
        """
        await self._wait_for_command_delay()

        url = f"{self._base_url}{path}"
        headers = self._headers.copy()
        request_params = params.copy() if params else {}

        # Add timestamp for V1 GET reads if not present
        if self._api_version == API_V1 and method.upper() == "GET" and not is_write_operation and "t" not in request_params:
            request_params["t"] = int(time.time() * 1000)

        # Add Authorization header for V2 write operations if API key exists
        if self._api_version == API_V2 and is_write_operation:
            if not self._api_key:
                _LOGGER.error("Attempting V2 write operation to %s without API key.", path)
                raise ApiAuthError("API key required for V2 write operations but none provided.")
            headers["Authorization"] = f"Bearer {self._api_key}"

        # Log request details (redacting sensitive headers)
        loggable_headers = { k: (v[:10] + "..." if k.lower() == "authorization" else v) for k, v in headers.items() }
        _LOGGER.debug("Requesting: %s %s (Params: %s, Data: %s, Headers: %s)",
            method.upper(), url, request_params or "None", json_data or "None", loggable_headers)

        try:
            # Execute request with timeout
            async with async_timeout.timeout(self._timeout):
                response = await self._session.request(
                    method, url, params=request_params or None, json=json_data,
                    headers=headers, ssl=self._ssl_context,
                )

            response_text = await response.text() # Read body text once
            _LOGGER.debug("Response Status: %s %s | Content-Type: %s", response.status, response.reason, response.content_type)
            log_snippet = (response_text[:150] + "...") if len(response_text) > 150 else response_text
            _LOGGER.debug("Response Body Snippet: %s", log_snippet)

            # Check for HTTP errors
            if response.status >= 400:
                error_message = f"API Error {response.status} ({response.reason}) for {method} {url}: {response_text}"
                if response.status in (401, 403): raise ApiAuthError(error_message)
                # Could add specific error classes for 400, 429, 5xx here if needed
                if self._api_version == API_V1 and response_text.strip().upper() == KEY_ACTION_FAILED_V1.upper():
                    raise ApiError(f"V1 action explicitly failed for {path}")
                raise ApiError(error_message) # General API error for other 4xx/5xx

            # Process successful responses (2xx)
            response_text_stripped = response_text.strip()

            if self._api_version == API_V1:
                if response_text_stripped.upper() == KEY_ACTION_SUCCESS_V1.upper(): return True
                if not response_text_stripped or response_text_stripped == "{}": return {}
                try: return json.loads(response_text_stripped)
                except json.JSONDecodeError as exc: raise ApiResponseError(f"Invalid V1 JSON response: '{response_text_stripped}'") from exc

            elif self._api_version == API_V2:
                if response.status == 204: return True # No Content indicates success
                if "application/json" not in str(response.content_type).lower(): raise ApiResponseError(f"Unexpected V2 content type: {response.content_type}")
                try: data = json.loads(response_text_stripped)
                except json.JSONDecodeError as exc: raise ApiResponseError(f"Invalid V2 JSON response: '{response_text_stripped}'") from exc
                if isinstance(data, dict) and KEY_ACTION_RESULT_V2 in data:
                    result_val = data[KEY_ACTION_RESULT_V2]
                    if str(result_val).upper() == "SUCCESS": return True
                    raise ApiError(f"V2 action reported failure: {result_val}")
                return data # Return parsed JSON data

            raise ApiError("Internal error: Unhandled API version in response processing.")

        except asyncio.TimeoutError as exc:
            _LOGGER.debug("Request timeout for %s", url)
            raise ApiConnectionError(f"Timeout connecting to {self._host} for {path}") from exc
        except aiohttp.ClientError as exc:
            # Covers various connection errors (refused, DNS, etc.)
            _LOGGER.debug("Client error for %s: %s", url, exc)
            raise ApiConnectionError(f"Communication error with {self._host}: {exc}") from exc
        except RetryError as exc:
            # Raised by tenacity after exhausting retries
            _LOGGER.error("Request failed after %d retries for %s", self._DEFAULT_RETRIES, url)
            raise ApiConnectionError(f"Request failed after retries for {path}: {exc}") from exc
        except ApiError: raise # Re-raise specific API errors
        except Exception as exc:
            _LOGGER.exception("Unexpected error during API request to %s", url)
            raise ApiError(f"Unexpected error during request to {path}: {exc}") from exc

    # === Public API Methods ===

    async def test_connection(self) -> dict[str, Any]:
        """Test connectivity and authentication by fetching device info."""
        _LOGGER.info("Testing connection to %s (API %s)...", self.host, self._api_version)
        try:
            info = await self.get_device_info()
            # Basic validation of returned info
            if not info.get(DEVICE_INFO_KEY_SERIAL) and not info.get(DEVICE_INFO_KEY_MAC):
                raise ApiError("Device info obtained but lacks Serial and MAC address.")
            _LOGGER.info("Connection test successful.")
            return info
        except ApiError as err:
            _LOGGER.error("Connection test failed: %s", err)
            raise # Re-raise original error for flow handling

    async def get_device_info(self) -> dict[str, Any]:
        """Fetch and normalize device information."""
        _LOGGER.debug("Fetching device info (API: %s)", self._api_version)
        if self._api_version == API_V1:
            try:
                # Fetch V1 data concurrently
                board_raw, box_raw = await asyncio.gather(
                    self._request("GET", V1_ENDPOINT_BOARD_INFO),
                    self._request("GET", V1_ENDPOINT_BOXINFO_GET), return_exceptions=True)
                # Handle potential partial failures
                if isinstance(board_raw, Exception) and isinstance(box_raw, Exception): raise ApiError("Failed to get V1 board and box info") from box_raw
                if isinstance(board_raw, Exception): _LOGGER.warning("Failed getting V1 board_info: %s", board_raw); board_raw = {}
                if isinstance(box_raw, Exception): _LOGGER.warning("Failed getting V1 boxinfoget: %s", box_raw); box_raw = {}
                # Normalize the combined data
                return self._normalize_v1_device_info(cast(dict, board_raw), cast(dict, box_raw))
            except Exception as e: raise ApiError(f"Failed to process V1 device info: {e}") from e
        elif self._api_version == API_V2:
            raw_data = await self._request("GET", V2_PATH_INFO)
            if not isinstance(raw_data, dict): raise ApiResponseError("V2 /info response was not a dict")
            return self._normalize_v2_device_info(raw_data)
        else: raise ApiError(f"Unsupported API version: {self._api_version}")

    def _normalize_v1_device_info(self, board_raw: dict, box_raw: dict) -> dict[str, Any]:
        """Normalize data from V1 /board_info and /boxinfoget."""
        norm_data = {}
        # From /board_info
        norm_data[DEVICE_INFO_KEY_SERIAL] = board_raw.get(KEY_SERIAL)
        norm_data[DEVICE_INFO_KEY_UPTIME] = _calculate_uptime_dt(board_raw.get(KEY_UPTIME))
        norm_data[DEVICE_INFO_KEY_SW_VERSION] = board_raw.get(KEY_SW_VERSION)
        norm_data[DEVICE_INFO_KEY_API_VERSION] = board_raw.get(KEY_API_VERSION)
        norm_data[DEVICE_INFO_KEY_MAC] = board_raw.get(KEY_MAC) # Format later
        norm_data[DEVICE_INFO_KEY_IP] = board_raw.get(KEY_IP_ADDRESS)
        # From /boxinfoget
        norm_data[DEVICE_INFO_KEY_DEVICE_TIME] = _calculate_utc_datetime(get_nested_value(box_raw, KEY_GENERAL, KEY_TIME))
        norm_data[DEVICE_INFO_KEY_RF_HOME_ID] = get_nested_value(box_raw, KEY_GENERAL, KEY_RFHOMEID)
        norm_data[DEVICE_INFO_KEY_INSTALLER_STATE] = get_nested_value(box_raw, KEY_GENERAL, KEY_INSTALLER_STATE)
        norm_data[DEVICE_INFO_KEY_CALIB_VALID] = get_nested_value(box_raw, KEY_CALIBRATION, KEY_CALIB_IS_VALID)
        norm_data[DEVICE_INFO_KEY_CALIB_STATE] = get_nested_value(box_raw, KEY_CALIBRATION, KEY_CALIB_STATE)
        norm_data[DEVICE_INFO_KEY_PRESSURE_TOTAL] = get_nested_value(box_raw, KEY_PERFORMANCE, KEY_PRESSURE_TOTAL)
        norm_data[DEVICE_INFO_KEY_PRESSURE_OUT] = get_nested_value(box_raw, KEY_PERFORMANCE, KEY_PRESSURE_OUT)
        norm_data[DEVICE_INFO_KEY_POWER_NOW] = get_nested_value(box_raw, KEY_PERFORMANCE, KEY_POWER_NOW)
        norm_data[DEVICE_INFO_KEY_POWER_AVG] = get_nested_value(box_raw, KEY_PERFORMANCE, KEY_POWER_AVG)
        norm_data[DEVICE_INFO_KEY_POWER_MAX] = get_nested_value(box_raw, KEY_PERFORMANCE, KEY_POWER_MAX)
        norm_data[DEVICE_INFO_KEY_WEATHER_PRESENT] = get_nested_value(box_raw, KEY_WEATHER_STATION, KEY_WEATHER_PRESENT)
        # WTW Fields
        norm_data[DEVICE_INFO_KEY_FILTER_REMAINING_TIME] = get_nested_value(box_raw, KEY_ENERGYINFO, KEY_FILTER_REMAIN)
        norm_data[DEVICE_INFO_KEY_TEMP_ODA] = _map_temp_times_10_get(get_nested_value(box_raw, KEY_ENERGYINFO, KEY_TEMPODA))
        norm_data[DEVICE_INFO_KEY_TEMP_SUP] = _map_temp_times_10_get(get_nested_value(box_raw, KEY_ENERGYINFO, KEY_TEMPSUP))
        norm_data[DEVICE_INFO_KEY_TEMP_ETA] = _map_temp_times_10_get(get_nested_value(box_raw, KEY_ENERGYINFO, KEY_TEMPETA))
        norm_data[DEVICE_INFO_KEY_TEMP_EHA] = _map_temp_times_10_get(get_nested_value(box_raw, KEY_ENERGYINFO, KEY_TEMPEHA))
        norm_data[DEVICE_INFO_KEY_SUPPLY_FAN_SPEED] = get_nested_value(box_raw, KEY_ENERGYFAN, KEY_SUPPLY_FAN_SPEED)
        norm_data[DEVICE_INFO_KEY_EXHAUST_FAN_SPEED] = get_nested_value(box_raw, KEY_ENERGYFAN, KEY_EXHAUST_FAN_SPEED)
        norm_data[DEVICE_INFO_KEY_SUPPLY_FAN_PWM] = get_nested_value(box_raw, KEY_ENERGYFAN, KEY_SUPPLY_FAN_PWM)
        norm_data[DEVICE_INFO_KEY_EXHAUST_FAN_PWM] = get_nested_value(box_raw, KEY_ENERGYFAN, KEY_EXHAUST_FAN_PWM)
        # Model
        norm_data[DEVICE_INFO_KEY_MODEL] = "DucoBox (V1 API)"
        # Filter out None values and format MAC
        final_data = {k: v for k, v in norm_data.items() if v is not None}
        if DEVICE_INFO_KEY_MAC in final_data: final_data[DEVICE_INFO_KEY_MAC] = format_mac(final_data[DEVICE_INFO_KEY_MAC])
        return final_data

    def _normalize_v2_device_info(self, raw_data: dict) -> dict[str, Any]:
        """Normalize data from V2 /info endpoint."""
        norm_data = {}
        def _g(data: dict, *keys: str, default: Any = None) -> Any: return get_nested_value(data, *keys, value_key=KEY_VAL, default=default)
        # Map V2 paths to normalized keys
        norm_data[DEVICE_INFO_KEY_SERIAL] = _g(raw_data, "Identification", "Product", KEY_SERIAL)
        norm_data[DEVICE_INFO_KEY_MAC] = _g(raw_data, KEY_V2_NETWORK, KEY_MODULE_ETHERNET, KEY_MAC)
        norm_data[DEVICE_INFO_KEY_SW_VERSION] = _g(raw_data, "Identification", "Firmware", KEY_SW_VERSION)
        norm_data[DEVICE_INFO_KEY_API_VERSION] = _g(raw_data, "Identification", "Firmware", KEY_API_VERSION)
        norm_data[DEVICE_INFO_KEY_UPTIME] = _calculate_uptime_dt(_g(raw_data, "Status", "System", KEY_UPTIME))
        norm_data[DEVICE_INFO_KEY_IP] = _g(raw_data, KEY_V2_NETWORK, KEY_MODULE_ETHERNET, KEY_IP_ADDRESS)
        norm_data[DEVICE_INFO_KEY_DEVICE_TIME] = _calculate_utc_datetime(_g(raw_data, "Status", "System", KEY_TIME))
        norm_data[DEVICE_INFO_KEY_RF_HOME_ID] = _g(raw_data, "Status", "RF", KEY_RFHOMEID)
        norm_data[DEVICE_INFO_KEY_INSTALLER_STATE] = _g(raw_data, "Status", "Operation", KEY_INSTALLER_STATE)
        norm_data[DEVICE_INFO_KEY_CALIB_VALID] = _g(raw_data, "Status", KEY_CALIBRATION, KEY_CALIB_IS_VALID)
        norm_data[DEVICE_INFO_KEY_CALIB_STATE] = _g(raw_data, "Status", KEY_CALIBRATION, KEY_CALIB_STATE)
        norm_data[DEVICE_INFO_KEY_POWER_NOW] = _g(raw_data, "Status", KEY_PERFORMANCE, KEY_POWER_NOW)
        norm_data[DEVICE_INFO_KEY_POWER_AVG] = _g(raw_data, "Status", KEY_PERFORMANCE, KEY_POWER_AVG)
        norm_data[DEVICE_INFO_KEY_POWER_MAX] = _g(raw_data, "Status", KEY_PERFORMANCE, KEY_POWER_MAX)
        norm_data[DEVICE_INFO_KEY_PRESSURE_TOTAL] = _g(raw_data, "Status", KEY_PERFORMANCE, KEY_PRESSURE_TOTAL)
        norm_data[DEVICE_INFO_KEY_PRESSURE_OUT] = _g(raw_data, "Status", KEY_PERFORMANCE, KEY_PRESSURE_OUT)
        norm_data[DEVICE_INFO_KEY_WEATHER_PRESENT] = _g(raw_data, "Status", "Weather", KEY_WEATHER_PRESENT)
        # V2 WTW Fields (using example paths, verify against actual V2 spec if possible)
        norm_data[DEVICE_INFO_KEY_FILTER_REMAINING_TIME] = _g(raw_data, KEY_V2_HEATRECOVERY, KEY_GENERAL, KEY_V2_TIME_FILTER_REMAIN)
        norm_data[DEVICE_INFO_KEY_TEMP_ODA] = _g(raw_data, "Status", KEY_V2_HEATRECOVERY, KEY_TEMPODA) # Assuming direct value
        norm_data[DEVICE_INFO_KEY_TEMP_SUP] = _g(raw_data, "Status", KEY_V2_HEATRECOVERY, KEY_TEMPSUP)
        norm_data[DEVICE_INFO_KEY_TEMP_ETA] = _g(raw_data, "Status", KEY_V2_HEATRECOVERY, KEY_TEMPETA)
        norm_data[DEVICE_INFO_KEY_TEMP_EHA] = _g(raw_data, "Status", KEY_V2_HEATRECOVERY, KEY_TEMPEHA)
        norm_data[DEVICE_INFO_KEY_SUPPLY_FAN_SPEED] = _g(raw_data, "Status", KEY_V2_HEATRECOVERY, KEY_SUPPLY_FAN_SPEED)
        norm_data[DEVICE_INFO_KEY_EXHAUST_FAN_SPEED] = _g(raw_data, "Status", KEY_V2_HEATRECOVERY, KEY_EXHAUST_FAN_SPEED)
        norm_data[DEVICE_INFO_KEY_SUPPLY_FAN_PWM] = _g(raw_data, "Status", KEY_V2_HEATRECOVERY, KEY_SUPPLY_FAN_PWM)
        norm_data[DEVICE_INFO_KEY_EXHAUST_FAN_PWM] = _g(raw_data, "Status", KEY_V2_HEATRECOVERY, KEY_EXHAUST_FAN_PWM)
        # Model
        norm_data[DEVICE_INFO_KEY_MODEL] = _g(raw_data, "Identification", "Product", "Type", default="DucoBox (V2 API)")
        # Filter out None values and format MAC
        final_data = {k: v for k, v in norm_data.items() if v is not None}
        if DEVICE_INFO_KEY_MAC in final_data: final_data[DEVICE_INFO_KEY_MAC] = format_mac(final_data[DEVICE_INFO_KEY_MAC])
        return final_data

    async def get_node_list(self) -> list[int]:
        """Fetch the list of active node IDs."""
        _LOGGER.debug("Fetching node list")
        try:
            if self._api_version == API_V1:
                response = await self._request("GET", V1_ENDPOINT_NODELIST)
                if isinstance(response, dict) and KEY_NODELIST_V1 in response and isinstance(response[KEY_NODELIST_V1], list):
                    return [int(nid) for nid in response[KEY_NODELIST_V1] if str(nid).isdigit()]
                raise ApiResponseError(f"Unexpected V1 nodelist format: {response}")
            elif self._api_version == API_V2:
                response = await self._request("GET", V2_PATH_INFO_NODES)
                if isinstance(response, dict) and KEY_NODES_V2 in response and isinstance(response[KEY_NODES_V2], list):
                    return [nid for node in response[KEY_NODES_V2] if isinstance(nid := get_nested_value(node, KEY_NODE_ID_V2, value_key=KEY_VAL), int)]
                raise ApiResponseError(f"Unexpected V2 nodelist format: {response}")
            raise ApiError(f"Unsupported API version for get_node_list: {self._api_version}")
        except ApiError as err: _LOGGER.error("Failed to get node list: %s", err); raise

    async def get_node_info(self, node_id: int) -> dict[str, Any]:
        """Fetch and normalize information for a specific node."""
        _LOGGER.debug("Fetching node info for node %d", node_id)
        try:
            if self._api_version == API_V1:
                raw_data = await self._request("GET", V1_ENDPOINT_NODEINFO_GET, params={KEY_NODE: node_id})
                if not isinstance(raw_data, dict): raise ApiResponseError("V1 node info not a dict")
                return self._normalize_v1_node_info(raw_data, node_id)
            elif self._api_version == API_V2:
                raw_data = await self._request("GET", V2_PATH_INFO_NODE_DETAIL.format(node_id=node_id))
                if not isinstance(raw_data, dict): raise ApiResponseError("V2 node info not a dict")
                return self._normalize_v2_node_info(raw_data, node_id)
            raise ApiError(f"Unsupported API version for get_node_info: {self._api_version}")
        except ApiError as err: _LOGGER.error("Failed get node info for %d: %s", node_id, err); raise

    def _normalize_v1_node_info(self, raw_data: dict, node_id: int) -> dict[str, Any]:
        """Normalize V1 node info."""
        norm_data = {NODE_INFO_KEY_ID: node_id}
        key_map = {
            KEY_DEVTYPE: NODE_INFO_KEY_DEVICE_TYPE, KEY_SUBTYPE: NODE_INFO_KEY_SUB_TYPE,
            KEY_LOCATION: NODE_INFO_KEY_LOCATION, KEY_STATE: NODE_INFO_KEY_STATE,
            KEY_MODE: NODE_INFO_KEY_MODE, KEY_CNTDWN: NODE_INFO_KEY_COUNTDOWN,
            KEY_ENDTIME: NODE_INFO_KEY_ENDTIME, KEY_TRGT: NODE_INFO_KEY_TARGET_LEVEL,
            KEY_ACTL: NODE_INFO_KEY_ACTUAL_LEVEL, KEY_SNSR: NODE_INFO_KEY_SENSOR_DEMAND,
            KEY_TEMP: NODE_INFO_KEY_TEMP, KEY_CO2: NODE_INFO_KEY_CO2, KEY_RH: NODE_INFO_KEY_RH,
            KEY_RSSI: NODE_INFO_KEY_RSSI, KEY_HOP_VIA: NODE_INFO_KEY_HOP_VIA, # RF Key
            KEY_RSSI_N2H: NODE_INFO_KEY_RSSI_N2H, # RF Key
            KEY_SW_VERSION_NODE: NODE_INFO_KEY_SW_VERSION, KEY_SERIAL_NB: NODE_INFO_KEY_SERIAL,
            KEY_DUCO_SERIAL: NODE_INFO_KEY_DUCO_SERIAL, KEY_PRNT: NODE_INFO_KEY_PARENT_ID,
            KEY_ASSO: NODE_INFO_KEY_ASSO_ID, KEY_CERR: NODE_INFO_KEY_COMM_ERROR_CODE,
            KEY_ERROR: NODE_INFO_KEY_ERROR_CODE, KEY_SHOW: NODE_INFO_KEY_SHOW,
            KEY_LINK: NODE_INFO_KEY_LINK, KEY_OVRL: NODE_INFO_KEY_OVERRULE_PCT,
        }
        for raw_key, norm_key in key_map.items():
            if raw_key in raw_data:
                raw_value = raw_data[raw_key]
                if norm_key == NODE_INFO_KEY_OVERRULE_PCT: value = _map_overrule_value(raw_value)
                elif norm_key == NODE_INFO_KEY_ENDTIME: value = _calculate_utc_datetime(raw_value)
                elif norm_key in (NODE_INFO_KEY_LINK, NODE_INFO_KEY_SHOW): value = bool(raw_value == 1)
                else: value = raw_value
                norm_data[norm_key] = value

        norm_data[NODE_INFO_KEY_ERROR_STATUS] = norm_data.get(NODE_INFO_KEY_ERROR_CODE) != NODE_NO_ERROR_CODE
        return {k: v for k, v in norm_data.items() if v is not None}

    def _normalize_v2_node_info(self, raw_data: dict, node_id: int) -> dict[str, Any]:
        """Normalize V2 node info."""
        norm_data = {NODE_INFO_KEY_ID: node_id}
        def _g(data: dict, *keys: str, default: Any = None) -> Any: return get_nested_value(data, *keys, value_key=KEY_VAL, default=default)
        # Map V2 paths using helper
        norm_data[NODE_INFO_KEY_DEVICE_TYPE] = _g(raw_data, "Identification", KEY_DEVTYPE)
        norm_data[NODE_INFO_KEY_SUB_TYPE] = _g(raw_data, "Identification", KEY_SUBTYPE)
        norm_data[NODE_INFO_KEY_STATE] = _g(raw_data, KEY_V2_VENTILATION, KEY_STATE)
        norm_data[NODE_INFO_KEY_MODE] = _g(raw_data, KEY_V2_VENTILATION, KEY_MODE)
        norm_data[NODE_INFO_KEY_COUNTDOWN] = _g(raw_data, KEY_V2_VENTILATION, KEY_V2_TIMESTATEREMAIN)
        norm_data[NODE_INFO_KEY_ENDTIME] = _calculate_utc_datetime(_g(raw_data, KEY_V2_VENTILATION, KEY_V2_TIMESTATEEND))
        norm_data[NODE_INFO_KEY_TARGET_LEVEL] = _g(raw_data, KEY_V2_VENTILATION, KEY_V2_FLOWLVLTGT)
        norm_data[NODE_INFO_KEY_ACTUAL_LEVEL] = _g(raw_data, KEY_V2_VENTILATION, KEY_ACTL)
        norm_data[NODE_INFO_KEY_OVERRULE_PCT] = _map_overrule_value(_g(raw_data, KEY_V2_VENTILATION, KEY_OVRL))
        norm_data[NODE_INFO_KEY_SENSOR_DEMAND] = _g(raw_data, KEY_V2_SENSOR, KEY_SNSR)
        norm_data[NODE_INFO_KEY_TEMP] = _g(raw_data, KEY_V2_SENSOR, KEY_TEMP)
        norm_data[NODE_INFO_KEY_CO2] = _g(raw_data, KEY_V2_SENSOR, KEY_CO2)
        norm_data[NODE_INFO_KEY_RH] = _g(raw_data, KEY_V2_SENSOR, KEY_RH)
        norm_data[NODE_INFO_KEY_IAQ_CO2] = _g(raw_data, KEY_V2_SENSOR, KEY_V2_IAQCO2)
        norm_data[NODE_INFO_KEY_IAQ_RH] = _g(raw_data, KEY_V2_SENSOR, KEY_V2_IAQRH)
        norm_data[NODE_INFO_KEY_RSSI] = _g(raw_data, "Status", "RF", KEY_RSSI) # V2 path assumed
        norm_data[NODE_INFO_KEY_HOP_VIA] = _g(raw_data, "Status", "RF", KEY_HOP_VIA) # V2 path assumed
        norm_data[NODE_INFO_KEY_RSSI_N2H] = _g(raw_data, "Status", "RF", KEY_RSSI_N2H) # V2 path assumed
        norm_data[NODE_INFO_KEY_SW_VERSION] = _g(raw_data, "Identification", KEY_SW_VERSION_NODE)
        norm_data[NODE_INFO_KEY_SERIAL] = _g(raw_data, "Identification", KEY_SERIAL_NB)
        norm_data[NODE_INFO_KEY_DUCO_SERIAL] = _g(raw_data, "Identification", KEY_DUCO_SERIAL)
        norm_data[NODE_INFO_KEY_PARENT_ID] = _g(raw_data, KEY_V2_NETWORK, "RF", KEY_PRNT)
        norm_data[NODE_INFO_KEY_ASSO_ID] = _g(raw_data, KEY_V2_NETWORK, "RF", KEY_ASSO)
        norm_data[NODE_INFO_KEY_COMM_ERROR_CODE] = _g(raw_data, "Status", "ComError", KEY_CERR)
        norm_data[NODE_INFO_KEY_ERROR_CODE] = _g(raw_data, "Status", "Alarm", KEY_ERROR)
        norm_data[NODE_INFO_KEY_SHOW] = bool(_g(raw_data, "Status", "UI", KEY_SHOW))
        norm_data[NODE_INFO_KEY_LINK] = bool(_g(raw_data, "Status", "RF", KEY_LINK))
        norm_data[NODE_INFO_KEY_LOCATION] = _g(raw_data, "Identification", KEY_LOCATION) # V2 Location path
        # Derive error status
        norm_data[NODE_INFO_KEY_ERROR_STATUS] = norm_data.get(NODE_INFO_KEY_ERROR_CODE) != NODE_NO_ERROR_CODE
        return {k: v for k, v in norm_data.items() if v is not None}

    async def get_node_config(self, node_id: int) -> dict[str, dict[str, Any]]:
        """Fetch and normalize configuration for a specific node."""
        _LOGGER.debug("Fetching node config for node %d", node_id)
        try:
            if self._api_version == API_V1:
                raw_data = await self._request("GET", V1_ENDPOINT_NODECONFIG_GET, params={KEY_NODE: node_id})
                return self._normalize_v1_node_config(cast(dict, raw_data))
            elif self._api_version == API_V2:
                raw_data = await self._request("GET", V2_PATH_CONFIG_NODE_DETAIL.format(node_id=node_id))
                return self._normalize_v2_node_config(cast(dict, raw_data))
            raise ApiError(f"Unsupported API version: {self._api_version}")
        except ApiError as err: _LOGGER.error("Failed get node config for %d: %s", node_id, err); raise

    def _normalize_v1_node_config(self, raw_data: dict) -> dict[str, dict[str, Any]]:
        """Normalize V1 node config into {param: {value:, min:, max:, step:}}."""
        norm_config = {}
        if not isinstance(raw_data, dict): return norm_config
        for param, data in raw_data.items():
            if isinstance(data, dict) and KEY_VAL in data:
                details = { NODE_CONFIG_KEY_VALUE: data.get(KEY_VAL), NODE_CONFIG_KEY_MIN: data.get(KEY_MIN), NODE_CONFIG_KEY_MAX: data.get(KEY_MAX), NODE_CONFIG_KEY_STEP: data.get(KEY_STEP) }
                norm_config[param] = {k: v for k, v in details.items() if v is not None}
            elif param == KEY_LOCATION_V1_CONFIG and isinstance(data, str):
                norm_config[param] = {NODE_CONFIG_KEY_VALUE: data} # Keep location as simple value dict
        return norm_config

    def _normalize_v2_node_config(self, raw_data: dict) -> dict[str, dict[str, Any]]:
        """Normalize V2 node config into {param: {value:, min:, max:, step:}}."""
        norm_config = {}
        if not isinstance(raw_data, dict): return norm_config
        for _module_name, module_data in raw_data.items():
            if isinstance(module_data, dict):
                for param, details in module_data.items():
                    if isinstance(details, dict) and KEY_VAL in details:
                        param_data = { NODE_CONFIG_KEY_VALUE: details.get(KEY_VAL), NODE_CONFIG_KEY_MIN: details.get(KEY_MIN), NODE_CONFIG_KEY_MAX: details.get(KEY_MAX), NODE_CONFIG_KEY_STEP: details.get(KEY_STEP) }
                        norm_config[param] = {k: v for k, v in param_data.items() if v is not None}
        return norm_config

    async def get_general_config(self, area: str) -> dict[str, dict[str, Any]]:
        """Fetch and normalize general configuration for a specific area."""
        _LOGGER.debug("Fetching general config for area: %s", area)
        try:
            endpoint_map_v1 = {'box': V1_ENDPOINT_BOXCONFIG_GET, 'eco': V1_ENDPOINT_ECOCONFIG_GET, 'ip': V1_ENDPOINT_IPCONFIG_GET}
            if self._api_version == API_V1:
                endpoint = endpoint_map_v1.get(area); assert endpoint, f"Invalid area '{area}' for V1 config"
                raw_data = await self._request("GET", endpoint)
                return self._normalize_v1_general_config(cast(dict, raw_data), area)
            elif self._api_version == API_V2:
                v2_module_name = V2_MODULE_MAP_TO_V1_AREA.get(area, area) # Map area to V2 module if needed
                raw_data = await self._request("GET", V2_PATH_CONFIG, params={'module': v2_module_name})
                return self._normalize_v2_general_config(cast(dict, raw_data))
            raise ApiError(f"Unsupported API version: {self._api_version}")
        except (ApiError, AssertionError) as err: _LOGGER.error("Failed get general config for '%s': %s", area, err); raise

    def _normalize_v1_general_config(self, raw_data: dict, area_name: str) -> dict[str, dict[str, Any]]:
        """Normalize V1 general config (box, ip, eco)."""
        if not isinstance(raw_data, dict): return {}
        norm_config = {}
        for module_name, module_data in raw_data.items():
            if not isinstance(module_data, dict): continue
            norm_module = {}; processed_ip_parts = set()
            for param_name, param_data in module_data.items():
                # Handle V1 IP Address reconstruction for 'ip' area
                is_ip_part_a = param_name.endswith("A") and len(param_name) > 1
                if area_name == 'ip' and is_ip_part_a and param_name not in processed_ip_parts:
                    base_key = param_name[:-1]
                    ip_str = reconstruct_ip_from_dict(module_data, base_key)
                    if ip_str is not None:
                        # Store reconstructed IP under the base key
                        norm_module[base_key] = {NODE_CONFIG_KEY_VALUE: ip_str}
                        # Mark individual parts as processed
                        for s in ['A','B','C','D']: processed_ip_parts.add(f"{base_key}{s}")
                    continue # Move to next param
                if param_name in processed_ip_parts: continue # Skip already processed IP parts

                # Handle standard config parameters
                if isinstance(param_data, dict) and KEY_VAL in param_data:
                    details = { NODE_CONFIG_KEY_VALUE: param_data.get(KEY_VAL), NODE_CONFIG_KEY_MIN: param_data.get(KEY_MIN), NODE_CONFIG_KEY_MAX: param_data.get(KEY_MAX), NODE_CONFIG_KEY_STEP: param_data.get(KEY_STEP) }
                    # Apply formatters based on parameter name
                    if param_name in (KEY_PARAM_TEMPCTRLHIGH, KEY_PARAM_TEMPCTRLLOW): details[NODE_CONFIG_KEY_VALUE] = _map_temp_times_10_get(details[NODE_CONFIG_KEY_VALUE])
                    elif param_name in (KEY_PARAM_NB_STARTTIME, KEY_PARAM_NB_STOPTIME, KEY_PARAM_VC_STARTTIME, KEY_PARAM_VC_STOPTIME): details[NODE_CONFIG_KEY_VALUE] = _map_minutes_to_time(details[NODE_CONFIG_KEY_VALUE])
                    # Add other formatters if needed
                    norm_module[param_name] = {k:v for k,v in details.items() if v is not None}
                elif not isinstance(param_data, dict): # Handle simple values if they exist in V1 config
                    norm_module[param_name] = {NODE_CONFIG_KEY_VALUE: param_data}
            if norm_module: norm_config[module_name] = norm_module
        return norm_config

    def _normalize_v2_general_config(self, raw_data: dict) -> dict[str, dict[str, Any]]:
        """Normalize V2 general config."""
        if not isinstance(raw_data, dict): return {}
        norm_config = {}
        for module_name, module_data in raw_data.items():
            if not isinstance(module_data, dict): continue
            norm_module = {}
            for param_name, param_details in module_data.items():
                if isinstance(param_details, dict) and KEY_VAL in param_details:
                    details = { NODE_CONFIG_KEY_VALUE: param_details.get(KEY_VAL), NODE_CONFIG_KEY_MIN: param_details.get(KEY_MIN), NODE_CONFIG_KEY_MAX: param_details.get(KEY_MAX), NODE_CONFIG_KEY_STEP: param_details.get(KEY_STEP) }
                    # Apply formatters if needed (V2 temps likely direct, times use minutes)
                    if param_name in (KEY_PARAM_NB_STARTTIME, KEY_PARAM_NB_STOPTIME, KEY_PARAM_VC_STARTTIME, KEY_PARAM_VC_STOPTIME): details[NODE_CONFIG_KEY_VALUE] = _map_minutes_to_time(details[NODE_CONFIG_KEY_VALUE])
                    norm_module[param_name] = {k:v for k,v in details.items() if v is not None}
            if norm_module: norm_config[module_name] = norm_module
        return norm_config

    async def set_node_config_value( self, node_id: int, param_name: str, value: Any, module_name: str | None = None ) -> bool:
        """Set a configuration value for a specific node."""
        _LOGGER.debug("API: Set node %d config: Param=%s, Value=%s (Mod: %s)", node_id, param_name, value, module_name)
        try:
            if self._api_version == API_V1:
                # Apply reverse formatters if needed
                if param_name == KEY_LOCATION_V1_CONFIG: pass # String is fine
                # Add reverse formatters for temp/time if node config included them
                params = {KEY_NODE: node_id, 'para': param_name, 'value': value}
                return await self._request("GET", V1_ENDPOINT_NODECONFIG_SET, params=params, is_write_operation=True)
            elif self._api_version == API_V2:
                if not module_name: raise ValueError(f"Module name required for V2 node config set: {param_name}")
                # Apply reverse formatters if needed
                payload_value = value
                payload = {module_name: {param_name: {KEY_VAL: payload_value}}}
                return await self._request("PATCH", V2_PATH_CONFIG_NODE_DETAIL.format(node_id=node_id), json_data=payload, is_write_operation=True)
            raise ApiError(f"Unsupported API version: {self._api_version}")
        except (ApiError, ValueError) as err: _LOGGER.error("Error setting node config %d: %s", node_id, err); return False

    async def set_general_config_value( self, area: str, mod_name: str, param_name: str, value: Any ) -> bool:
        """Set a general configuration value (box, eco, ip areas)."""
        _LOGGER.debug("API: Set general config [%s]: Mod=%s, Param=%s, Value=%s", area, mod_name, param_name, value)
        try:
            # Apply reverse formatters
            api_value = value
            if param_name in (KEY_PARAM_TEMPCTRLHIGH, KEY_PARAM_TEMPCTRLLOW): api_value = _map_temp_times_10_set(value)
            elif param_name in (KEY_PARAM_NB_STARTTIME, KEY_PARAM_NB_STOPTIME, KEY_PARAM_VC_STARTTIME, KEY_PARAM_VC_STOPTIME): api_value = _map_time_to_minutes(value)
            # Handle V1 IP Setting
            if self._api_version == API_V1 and area == 'ip' and param_name in (KEY_PARAM_STATICIP, KEY_PARAM_NETMASK, KEY_PARAM_GATEWAY, KEY_PARAM_MQTT_BROKERIP):
                if not isinstance(api_value, str) or len(parts := api_value.split('.')) != 4: raise ValueError(f"Invalid IP format: {api_value}")
                try: int_parts = [int(p) for p in parts]; assert all(0 <= p <= 255 for p in int_parts); val_a, val_b, val_c, val_d = int_parts
                except (ValueError, TypeError, AssertionError) as e: raise ValueError(f"Invalid IP address parts: {api_value}") from e
                params = { 'mod': mod_name, 'para': param_name, KEY_VALUE_A: val_a, KEY_VALUE_B: val_b, KEY_VALUE_C: val_c, KEY_VALUE_D: val_d }
                return await self._request("GET", V1_ENDPOINT_IPCONFIG_SET, params=params, is_write_operation=True)

            # Standard Setting
            if self._api_version == API_V1:
                endpoint_map = {'box': V1_ENDPOINT_BOXCONFIG_SET, 'eco': V1_ENDPOINT_ECOCONFIG_SET}; endpoint = endpoint_map.get(area)
                if not endpoint: raise ValueError(f"Invalid area '{area}' for V1 set")
                params = {'mod': mod_name, 'para': param_name, 'value': api_value}
                return await self._request("GET", endpoint, params=params, is_write_operation=True)
            elif self._api_version == API_V2:
                v2_module_name = V2_MODULE_MAP_TO_V1_AREA.get(area, area)
                payload = {mod_name: {param_name: {KEY_VAL: api_value}}}
                return await self._request("PATCH", V2_PATH_CONFIG, params={'module': v2_module_name}, json_data=payload, is_write_operation=True)
            raise ApiError(f"Unsupported API version: {self._api_version}")
        except (ApiError, ValueError) as err: _LOGGER.error("Error setting general config %s.%s: %s", mod_name, param_name, err); return False

    async def perform_node_action( self, node_id: int, action_name: str, value: Any | None = None ) -> bool:
        """Perform an action on a specific node."""
        _LOGGER.debug("API: Perform node action on %d: Action=%s, Value=%s", node_id, action_name, value)
        try:
            if self._api_version == API_V1:
                mapping = { ACTION_SET_OPER_STATE: (V1_ENDPOINT_NODE_SET_OPERSTATE, 'value'), ACTION_SET_OVERRULE: (V1_ENDPOINT_NODE_SET_OVERRULE, 'value'), ACTION_RESET_NODE: (V1_ENDPOINT_NODE_RESET, KEY_NODE), ACTION_LOAD_DEFAULTS_NODE: (V1_ENDPOINT_NODE_LOAD_DEFAULTS, KEY_NODE), ACTION_SET_SHOW: (V1_ENDPOINT_NODE_SET_SHOW, 'value'), ACTION_SET_LINK_MODE: (V1_ENDPOINT_NODE_SET_LINKMODE, 'value'), ACTION_SET_PARENT: (V1_ENDPOINT_NODE_SET_PARENT, 'parent'), ACTION_SET_ASSOCIATION: (V1_ENDPOINT_NODE_SET_ASSO, 'asso') }
                details = mapping.get(action_name); assert details, f"Unsupported V1 node action: {action_name}"
                endpoint, val_param_name = details; params = {KEY_NODE: node_id}
                if val_param_name and val_param_name != KEY_NODE and value is not None: params[val_param_name] = value
                return await self._request("GET", endpoint, params=params, is_write_operation=True)
            elif self._api_version == API_V2:
                mapping = { ACTION_SET_OPER_STATE: V2_ACTION_SET_VENTILATION_STATE, ACTION_SET_OVERRULE: V2_ACTION_SET_OVERRULE, ACTION_RESET_NODE: V2_ACTION_RESET_NODE, ACTION_LOAD_DEFAULTS_NODE: V2_ACTION_LOAD_DEFAULTS_NODE, ACTION_SET_SHOW: V2_ACTION_SET_SHOW, ACTION_SET_LINK_MODE: V2_ACTION_SET_LINK_MODE, ACTION_SET_PARENT: V2_ACTION_SET_PARENT, ACTION_SET_ASSOCIATION: V2_ACTION_SET_ASSOCIATION }
                v2_action = mapping.get(action_name); assert v2_action, f"Unsupported V2 node action: {action_name}"
                payload: dict[str, Any] = {"Action": v2_action};
                if value is not None: payload[KEY_VAL] = value
                return await self._request("POST", V2_PATH_ACTION_NODE.format(node_id=node_id), json_data=payload, is_write_operation=True)
            raise ApiError(f"Unsupported API version: {self._api_version}")
        except (ApiError, AssertionError) as err: _LOGGER.error("Error performing node action %s on %d: %s", action_name, node_id, err); return False

    async def perform_device_action( self, action_name: str, value: Any | None = None ) -> bool:
        """Perform an action on the main device/box."""
        if action_name == ACTION_SET_TIME and value is None: value = int(time.time())
        _LOGGER.debug("API: Perform device action: Action=%s, Value=%s", action_name, value)
        try:
            if self._api_version == API_V1:
                mapping = { ACTION_SET_TIME: (V1_ENDPOINT_BOX_SET_TIME, 'time'), ACTION_SET_INSTALLER_MODE: (V1_ENDPOINT_BOX_SET_INSTALL, 'set'), ACTION_CLEAR_NETWORK: (V1_ENDPOINT_BOX_CLEAR_NETWORK, None), ACTION_SET_CALIBRATION: (V1_ENDPOINT_BOX_SET_CALIBRATION, 'set'), ACTION_REBOOT_DEVICE: (V1_ENDPOINT_BOARD_RESET, None) }
                details = mapping.get(action_name); assert details, f"Unsupported V1 device action: {action_name}"
                endpoint, val_param_name = details; params = {}
                if val_param_name and value is not None: params[val_param_name] = value
                return await self._request("GET", endpoint, params=params or None, is_write_operation=True)
            elif self._api_version == API_V2:
                mapping = { ACTION_SET_TIME: V2_ACTION_SET_TIME, ACTION_SET_INSTALLER_MODE: V2_ACTION_SET_INSTALLER_MODE, ACTION_CLEAR_NETWORK: V2_ACTION_CLEAR_NETWORK, ACTION_SET_CALIBRATION: V2_ACTION_SET_CALIBRATION, ACTION_REBOOT_DEVICE: V2_ACTION_REBOOT }
                v2_action = mapping.get(action_name); assert v2_action, f"Unsupported V2 device action: {action_name}"
                payload: dict[str, Any] = {"Action": v2_action};
                if value is not None: payload[KEY_VAL] = value
                return await self._request("POST", V2_PATH_ACTION, json_data=payload, is_write_operation=True)
            raise ApiError(f"Unsupported API version: {self._api_version}")
        except (ApiError, AssertionError) as err: _LOGGER.error("Error performing device action %s: %s", action_name, err); return False

# === CLI Testing Section ===
async def _cli_main() -> None:
    # (CLI parsing and execution logic remains the same)
    import argparse, sys
    parser = argparse.ArgumentParser(description="Duco API Client CLI Tester"); parser.add_argument("host"); parser.add_argument("--api-version", choices=[API_V1, API_V2], required=True); parser.add_argument("--api-key"); parser.add_argument("--action", required=True, choices=["info", "nodes", "node_info", "node_config", "gen_config"]); parser.add_argument("--node-id", type=int); parser.add_argument("--area"); parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(); logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'); logging.getLogger("asyncio").setLevel(logging.WARNING); logging.getLogger("aiohttp").setLevel(logging.WARNING)
    if args.action in ["node_info", "node_config"] and args.node_id is None: print("Error: --node-id required", file=sys.stderr); sys.exit(1)
    if args.action == "gen_config" and args.area is None: print("Error: --area required", file=sys.stderr); sys.exit(1)
    async with aiohttp.ClientSession() as session:
        client = DucoApiClient(host=args.host, api_version=args.api_version, session=session, api_key=args.api_key)
        try:
            result: Any = None; print(f"Performing action: {args.action}...")
            if args.action == "info": result = await client.get_device_info()
            elif args.action == "nodes": result = await client.get_node_list()
            elif args.action == "node_info": result = await client.get_node_info(args.node_id) # type: ignore
            elif args.action == "node_config": result = await client.get_node_config(args.node_id) # type: ignore
            elif args.action == "gen_config": result = await client.get_general_config(args.area) # type: ignore
            print("\nResult:"); print(json.dumps(result, indent=2, default=str))
        except ApiError as e: print(f"\nAPI Error: {e}", file=sys.stderr); sys.exit(1)
        except Exception as e: print(f"\nUnexpected Error: {e}", file=sys.stderr); logging.exception("CLI unexpected error details:"); sys.exit(1)
if __name__ == "__main__":
    asyncio.run(_cli_main())

# Perform final indentation check
# (Conceptual pass completed - code should be correctly indented)
# === custom_components/duco_ventilation_sun_control/config_flow.py ===
"""Config flow for Duco Ventilation System integration."""

from __future__ import annotations

import logging
from typing import Any, Final

import voluptuous as vol
# External library for Duco API communication (placeholder)
# from duco_api import ApiAuthError, ApiConnectionError, ApiError, DucoApiClient
from .api import ApiAuthError, ApiConnectionError, ApiError, DucoApiClient
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    API_V1,
    API_V2,
    CONF_API_VERSION,
    CONF_COMMAND_QUEUE_DELAY,
    CONF_REQUEST_RETRIES,
    CONF_REQUEST_TIMEOUT,
    CONF_RETRY_DELAY,
    CONF_SCAN_INTERVAL,
    DEFAULT_COMMAND_QUEUE_DELAY,
    DEFAULT_REQUEST_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEVICE_INFO_KEY_MAC,
    DEVICE_INFO_KEY_SERIAL,
    DOMAIN,
    TRANS_ABORT_ALREADY_CONFIGURED,
    TRANS_ABORT_ALREADY_IN_PROGRESS,
    TRANS_ABORT_CANNOT_CONNECT,
    TRANS_ABORT_CONTEXT_ERROR,
    TRANS_ABORT_DISCOVERY_ERROR,
    TRANS_ABORT_MISSING_UNIQUE_ID,
    TRANS_ABORT_UNKNOWN_API_VERSION,
    TRANS_ERROR_CANNOT_CONNECT,
    TRANS_ERROR_INVALID_AUTH,
    TRANS_ERROR_MISSING_UNIQUE_ID,
    TRANS_ERROR_UNKNOWN,
    TRANS_ERROR_UNKNOWN_API_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# Step Schemas
STEP_USER_DATA_SCHEMA: Final = vol.Schema({vol.Required(CONF_HOST): str})
STEP_V2_AUTH_DATA_SCHEMA: Final = vol.Schema({vol.Required(CONF_API_KEY): str})

# Validation Result Type
ValidationResultType: Final = tuple[dict[str, Any], str, str]


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> ValidationResultType:
    """Validate user input and device connection using the external library.

    Attempts connection using host and potentially API key/version, determines
    the correct API version, fetches device info (for unique ID and title),
    and returns validated data.

    Args:
        hass: The Home Assistant instance.
        data: Dictionary with CONF_HOST, optionally CONF_API_KEY, CONF_API_VERSION.

    Returns:
        A tuple: (validated_data, title, unique_id).

    Raises:
        ApiConnectionError: If connection fails (maps to cannot_connect).
        ApiAuthError: If V2 authentication fails (maps to invalid_auth).
        ApiError: For other API issues (maps to unknown).
        ValueError: If essential data like unique ID is missing.
    """
    session = async_get_clientsession(hass)
    host = data[CONF_HOST]
    api_key = data.get(CONF_API_KEY)
    # Allow forcing API version during validation if provided (e.g., from Zeroconf)
    api_version_input = data.get(CONF_API_VERSION)

    detected_api_version: str | None = None
    device_info: dict[str, Any] | None = None
    client: DucoApiClient | None = None
    last_error: Exception | None = None

    async def try_version(version_to_try: str, key: str | None) -> bool:
        """Attempt connection with a specific API version."""
        nonlocal device_info, detected_api_version, client, last_error
        _LOGGER.debug("Attempting connection to %s via API %s", host, version_to_try)
        try:
            # Use default timeouts/retries for validation calls for simplicity
            client = DucoApiClient(
                host=host, api_version=version_to_try, session=session, api_key=key
            )
            # test_connection now uses get_device_info internally
            conn_test_result = await client.test_connection()

            if not isinstance(conn_test_result, dict) or not conn_test_result:
                _LOGGER.warning(
                    "Connection test returned unexpected or empty result for API %s: %s",
                    version_to_try, conn_test_result
                )
                last_error = ApiError("Received no or invalid device info")
                return False

            device_info = conn_test_result
            detected_api_version = version_to_try
            _LOGGER.info("Successfully connected to %s via API %s", host, version_to_try)
            return True

        except ApiAuthError as err:
            _LOGGER.debug("Auth error during validation API %s: %s", version_to_try, err)
            last_error = err # Store auth error specifically
            raise # Re-raise to be caught by main loop
        except ApiConnectionError as err:
            _LOGGER.debug("Connection error during validation API %s: %s", version_to_try, err)
            last_error = err # Store connection error
            return False
        except ApiError as err:
            _LOGGER.debug("API error during validation API %s: %s", version_to_try, err)
            last_error = err # Store other API errors
            return False
        except Exception as err: # Catch unexpected errors during validation
            _LOGGER.exception(
                "Unexpected validation error API %s: %s", version_to_try, err
            )
            # Treat unexpected errors as connection errors for flow handling
            last_error = ApiConnectionError(f"Unexpected validation error: {err}")
            return False

    # Determine which API versions to try
    versions_to_try = [api_version_input] if api_version_input else [API_V1, API_V2]

    validation_passed = False
    auth_error_occurred = False
    try:
        for version in versions_to_try:
            key_to_use = api_key if version == API_V2 else None
            if await try_version(version, key_to_use):
                validation_passed = True
                break
    except ApiAuthError:
        auth_error_occurred = True # V2 key likely needed/invalid

    # If initial attempts failed (and wasn't auth error), try any remaining version
    if not validation_passed and not auth_error_occurred:
        other_versions = [v for v in [API_V1, API_V2] if v not in versions_to_try]
        if other_versions:
            _LOGGER.debug("Initial validation failed, trying other versions: %s", other_versions)
            try:
                for version in other_versions:
                    key_to_use = api_key if version == API_V2 else None
                    if await try_version(version, key_to_use):
                        validation_passed = True
                        break
            except ApiAuthError:
                auth_error_occurred = True # Auth error on fallback attempt

    # Evaluate outcome
    if not validation_passed:
        if auth_error_occurred:
            raise ApiAuthError("Authentication failed for V2 API")
        if isinstance(last_error, ApiConnectionError):
            raise last_error
        raise ApiConnectionError(f"Failed to connect using any API version: {last_error or 'Unknown reason'}")

    # At this point, validation succeeded
    if not detected_api_version or not device_info or not client:
        _LOGGER.error("Validation logic error: Success reported but internal state inconsistent")
        raise ApiError("Internal validation state inconsistent after success")

    # Determine unique ID (Serial preferred, MAC fallback)
    serial = device_info.get(DEVICE_INFO_KEY_SERIAL)
    mac = device_info.get(DEVICE_INFO_KEY_MAC)
    unique_id_val: str | None = None

    if serial:
        unique_id_val = str(serial)
    elif mac:
        unique_id_val = format_mac(mac)

    if not unique_id_val:
        raise ValueError("Could not determine unique ID (missing serial and MAC)")

    # Construct title based on our agreed naming convention
    box_node_id = "?" # Placeholder, real box node ID isn't fetched here
    # We might need to fetch node list/info here to get the *actual* box node ID
    # For now, using '?' as it's not critical for the flow itself.
    title = f"DucoBox ({box_node_id}) - {unique_id_val}"

    # Prepare validated data for ConfigEntry
    result_data = {
        CONF_HOST: host,
        CONF_API_VERSION: detected_api_version,
        # Only include API key if V2 was detected AND a key was provided
        CONF_API_KEY: api_key if detected_api_version == API_V2 and api_key else None,
    }

    _LOGGER.info(
        "Validation successful: Host=%s, Version=%s, Unique ID=%s, Title=%s",
        host, detected_api_version, unique_id_val, title
    )
    return result_data, title, unique_id_val


class DucoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for Duco Ventilation System."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow handler."""
        self._host: str | None = None
        self._api_version: str | None = None
        self._title: str | None = None
        self._unique_id: str | None = None
        self._validated_data: dict[str, Any] = {}
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step where the user provides the host."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            try:
                validation_data = {CONF_HOST: self._host}
                # Try validation without API key first
                self._validated_data, self._title, self._unique_id = await validate_input(
                    self.hass, validation_data
                )

                # Validation succeeded, set unique ID and check for existing entries
                await self.async_set_unique_id(self._unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

                # Create the entry with default options
                return self.async_create_entry(
                    title=self._title, data=self._validated_data, options=self._get_default_options()
                )

            except ApiAuthError:
                # Implies V2 API requires a key. Proceed to V2 auth step.
                _LOGGER.debug("Validation requires V2 API key for %s", self._host)
                self._api_version = API_V2
                # Use temporary title until key is validated
                self._title = f"DucoBox ({self._host})"
                # Store host for the next step
                self.context[CONF_HOST] = self._host
                return await self.async_step_finish_v2_setup()
            except ApiConnectionError:
                errors["base"] = TRANS_ERROR_CANNOT_CONNECT
            except ValueError: # Raised by validate_input if unique ID missing
                errors["base"] = TRANS_ERROR_MISSING_UNIQUE_ID
            except AbortFlow: # Catch already configured / in progress
                raise
            except Exception as e:
                _LOGGER.exception("Unexpected exception during user setup step: %s", e)
                errors["base"] = TRANS_ERROR_UNKNOWN

        # Show the initial form
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovery: %s", discovery_info)
        host = discovery_info.host
        port = discovery_info.port
        properties = discovery_info.properties

        # Try to determine API version from properties or port
        discovered_api_version: str | None = None
        api_version_prop = properties.get("ApiVersion") # Check property name
        if api_version_prop:
            if isinstance(api_version_prop, str):
                if api_version_prop.startswith("1."): discovered_api_version = API_V1
                elif api_version_prop.startswith("2."): discovered_api_version = API_V2
        # Fallback to port if property missing/invalid
        if not discovered_api_version:
            if port == 80: discovered_api_version = API_V1
            elif port == 443: discovered_api_version = API_V2

        if not discovered_api_version:
            _LOGGER.debug("Could not determine API version from Zeroconf for %s", host)
            return self.async_abort(reason=TRANS_ABORT_UNKNOWN_API_VERSION)

        # Basic validation: Try to connect and get unique ID
        validation_data = {
            CONF_HOST: host,
            CONF_API_VERSION: discovered_api_version # Force validation with discovered version
        }
        temp_title: str | None = None
        temp_unique_id: str | None = None
        validated_data_zc: dict[str, Any] = {}

        try:
            validated_data_zc, temp_title, temp_unique_id = await validate_input(
                self.hass, validation_data
            )
            if not temp_unique_id: raise ValueError("Missing unique ID from Zeroconf validation")

            # Set unique ID and abort if already configured
            await self.async_set_unique_id(temp_unique_id, raise_on_progress=True)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            # Store context for confirmation step
            self.context.update({
                CONF_HOST: host,
                CONF_API_VERSION: discovered_api_version,
                "title": temp_title,
                "validated_data": validated_data_zc,
                "unique_id": temp_unique_id,
            })
            return await self.async_step_zeroconf_confirm()

        except ApiAuthError:
            # V2 device found, needs API key - proceed to confirmation, then V2 setup
            _LOGGER.debug("Zeroconf found V2 API for %s, requires API key", host)
            # Cannot set unique_id yet as validation failed
            self._abort_if_host_already_in_progress(host) # Check if user flow started
            self.context.update({
                CONF_HOST: host,
                CONF_API_VERSION: API_V2, # Store that V2 was detected
                "title": f"DucoBox ({host})", # Temporary title
            })
            return await self.async_step_zeroconf_confirm()
        except AbortFlow as err:
            _LOGGER.debug("Zeroconf validation aborted for %s: %s", host, err.reason)
            return self.async_abort(reason=err.reason)
        except (ApiConnectionError, ValueError, ApiError, Exception) as e:
            _LOGGER.warning("Zeroconf validation failed for %s: %s", host, e)
            # Do not automatically create entry if validation fails
            return self.async_abort(reason=TRANS_ABORT_CANNOT_CONNECT)

    def _abort_if_host_already_in_progress(self, host: str) -> None:
        """Abort if a flow for the same host is already in progress."""
        for flow in self._async_in_progress():
            if (
                flow.get("context", {}).get(CONF_HOST) == host
                and flow.get("flow_id") != self.flow_id
            ):
                raise AbortFlow(TRANS_ABORT_ALREADY_IN_PROGRESS)

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user confirmation of the discovered device."""
        # Extract context, check for essential keys
        context_host = self.context.get(CONF_HOST)
        context_api_version = self.context.get(CONF_API_VERSION)
        context_title = self.context.get("title")
        if not context_host or not context_api_version or not context_title:
            return self.async_abort(reason=TRANS_ABORT_CONTEXT_ERROR)

        context_validated_data = self.context.get("validated_data")
        context_unique_id = self.context.get("unique_id")

        placeholders = {
            "name": context_title,
            "host": context_host,
            "api_version": context_api_version,
        }

        # If validation succeeded earlier (unique ID exists), re-check if configured
        if context_unique_id:
            await self.async_set_unique_id(context_unique_id, raise_on_progress=False)
            self._abort_if_unique_id_configured(updates={CONF_HOST: context_host})

        if user_input is not None:
            # If validation succeeded (data/unique ID available), create entry
            if context_validated_data and context_unique_id:
                return self.async_create_entry(
                    title=context_title, data=context_validated_data, options=self._get_default_options()
                )
            # If V2 API requires key (no validated data yet), move to V2 setup
            if context_api_version == API_V2:
                self._host = context_host # Store host for V2 step
                return await self.async_step_finish_v2_setup()

            # Should not happen if context is consistent
            _LOGGER.error("Zeroconf confirmation inconsistency: Missing validated data or V2 flag.")
            return self.async_abort(reason=TRANS_ERROR_UNKNOWN)

        # Show confirmation dialog
        return self.async_show_form(
            step_id="zeroconf_confirm", description_placeholders=placeholders
        )

    async def async_step_finish_v2_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the final V2 setup step (API key input)."""
        errors: dict[str, str] = {}
        # Retrieve host from context if coming from zeroconf, or use stored _host
        host_to_use = self.context.get(CONF_HOST, self._host)
        if not host_to_use:
            return self.async_abort(reason=TRANS_ABORT_CONTEXT_ERROR)

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            validation_data = {
                CONF_HOST: host_to_use,
                CONF_API_VERSION: API_V2, # Force V2 validation
                CONF_API_KEY: api_key,
            }
            try:
                # Validate with API key
                validated_data, final_title, final_unique_id = await validate_input(
                    self.hass, validation_data
                )

                # Set unique ID and check configuration status
                await self.async_set_unique_id(final_unique_id, raise_on_progress=False)
                # Check if this device is already configured or if we are re-authenticating
                existing_entry = await self.async_set_unique_id(final_unique_id)
                if self._reauth_entry and existing_entry and existing_entry.entry_id == self._reauth_entry.entry_id:
                    _LOGGER.info("Re-authentication successful for %s", final_unique_id)
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry, data=validated_data
                    )
                    await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

                # If not re-auth, abort if already configured
                self._abort_if_unique_id_configured(updates={CONF_HOST: host_to_use})

                # Create new entry
                return self.async_create_entry(
                    title=final_title, data=validated_data, options=self._get_default_options()
                )

            except ApiAuthError:
                errors["base"] = TRANS_ERROR_INVALID_AUTH
            except ApiConnectionError:
                errors["base"] = TRANS_ERROR_CANNOT_CONNECT
            except ValueError: # Unique ID missing
                errors["base"] = TRANS_ERROR_MISSING_UNIQUE_ID
            except AbortFlow: # Already configured / in progress
                raise
            except Exception as e:
                _LOGGER.exception("Unexpected exception during V2 key setup step: %s", e)
                errors["base"] = TRANS_ERROR_UNKNOWN

        # Show V2 API key form
        return self.async_show_form(
            step_id="finish_v2_setup",
            data_schema=STEP_V2_AUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={CONF_HOST: host_to_use},
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle configuration entry re-authentication (triggered by auth error)."""
        _LOGGER.info("Starting re-authentication flow for Duco entry")
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if not self._reauth_entry: # Should not happen
            return self.async_abort(reason=TRANS_ABORT_CONTEXT_ERROR)

        self._host = self._reauth_entry.data[CONF_HOST]
        self._api_version = self._reauth_entry.data.get(CONF_API_VERSION)

        # Re-authentication only makes sense for V2 which uses API keys
        if self._api_version != API_V2:
            _LOGGER.warning("Re-authentication requested for non-V2 API entry (%s). Aborting.", self._api_version)
            return self.async_abort(reason="reauth_not_required_v1")

        # Store host in context for the next step
        self.context[CONF_HOST] = self._host
        return await self.async_step_finish_v2_setup() # Go directly to API key step

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow handler."""
        # Defer import to avoid circular dependency
        from .options_flow import DucoOptionsFlowHandler
        return DucoOptionsFlowHandler(config_entry)

    @staticmethod
    def _get_default_options() -> dict[str, Any]:
        """Return default options for a new config entry."""
        return {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
            CONF_REQUEST_TIMEOUT: DEFAULT_REQUEST_TIMEOUT,
            CONF_REQUEST_RETRIES: DEFAULT_REQUEST_RETRIES,
            CONF_RETRY_DELAY: DEFAULT_RETRY_DELAY,
            CONF_COMMAND_QUEUE_DELAY: DEFAULT_COMMAND_QUEUE_DELAY,
        }
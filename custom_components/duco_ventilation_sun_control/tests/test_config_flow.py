# === tests/test_config_flow.py ===
"""Test the Duco Ventilation System config flow."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.duco_ventilation_sun_control.api import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
)
from custom_components.duco_ventilation_sun_control.const import (
    API_V1,
    API_V2,
    DOMAIN,
)

# Import mock data and fixtures from conftest
from .conftest import (
    MOCK_API_KEY_V2,
    MOCK_CONFIG_DATA_V1,
    MOCK_CONFIG_DATA_V2,
    MOCK_DEVICE_INFO_V1,
    MOCK_DEVICE_INFO_V2,
    MOCK_HOST_V1,
    MOCK_HOST_V2,
    MOCK_MAC,
    MOCK_SERIAL,
    MOCK_USER_INPUT_V1,
    MOCK_USER_INPUT_V2,
    MOCK_USER_INPUT_V2_WITH_KEY,
)


# === Test User Flow ===

async def test_user_flow_success_v1(
    hass: HomeAssistant, mock_duco_api_client: MagicMock
) -> None:
    """Test successful user setup for a V1 device."""
    # Configure mock API client for V1 success
    mock_duco_api_client.test_connection.return_value = MOCK_DEVICE_INFO_V1
    # Since test_connection calls get_device_info internally in the mock structure:
    mock_duco_api_client.get_device_info.return_value = MOCK_DEVICE_INFO_V1
    # Assume V1 validation succeeds first try
    mock_duco_api_client._api_version = API_V1 # Simulate client knowing version

    # Initiate the user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    # Provide host input
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT_V1
    )
    await hass.async_block_till_done() # Allow tasks to complete

    # Check that the flow finished and created an entry
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"DucoBox (?) - {MOCK_SERIAL}" # Using default naming pattern
    assert result2["data"] == MOCK_CONFIG_DATA_V1
    assert result2["options"] is not None # Should have default options
    # Verify API call
    mock_duco_api_client.test_connection.assert_awaited_once()


async def test_user_flow_success_v2(
    hass: HomeAssistant, mock_duco_api_client: MagicMock
) -> None:
    """Test successful user setup for a V2 device requiring API key."""
    # Configure mock API client: First attempt (V1 or V2 w/o key) fails with auth error,
    # second attempt (V2 w/ key) succeeds.
    mock_duco_api_client.test_connection.side_effect = [
        ApiAuthError("API key required"), # First call in validate_input fails
        MOCK_DEVICE_INFO_V2,              # Second call in finish_v2_setup succeeds
    ]
    # Simulate get_device_info being called internally
    mock_duco_api_client.get_device_info.return_value = MOCK_DEVICE_INFO_V2

    # Initiate user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Provide host input (V2 host)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT_V2
    )
    await hass.async_block_till_done()

    # Should proceed to finish_v2_setup step
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "finish_v2_setup"
    assert result2["errors"] is None

    # Provide API key
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {CONF_API_KEY: MOCK_API_KEY_V2}
    )
    await hass.async_block_till_done()

    # Check that flow finished and created V2 entry
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == f"DucoBox (?) - {MOCK_SERIAL}"
    assert result3["data"] == MOCK_CONFIG_DATA_V2
    assert result3["options"] is not None
    # Verify API calls (initial fail + success with key)
    assert mock_duco_api_client.test_connection.call_count == 2


async def test_user_flow_connection_error(
    hass: HomeAssistant, mock_duco_api_client: MagicMock
) -> None:
    """Test user setup with a connection error during validation."""
    mock_duco_api_client.test_connection.side_effect = ApiConnectionError("Timeout")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT_V1
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(
    hass: HomeAssistant, mock_duco_api_client: MagicMock
) -> None:
    """Test user setup with an unknown error during validation."""
    mock_duco_api_client.test_connection.side_effect = ApiError("Unexpected API response")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT_V1
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    # ApiError maps to cannot_connect in validation's exception handling for user flow start
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_missing_id_error(
    hass: HomeAssistant, mock_duco_api_client: MagicMock
) -> None:
    """Test user setup where device info lacks unique identifiers."""
    mock_device_info_no_id = MOCK_DEVICE_INFO_V1.copy()
    del mock_device_info_no_id["serial"]
    del mock_device_info_no_id["mac"]
    mock_duco_api_client.test_connection.return_value = mock_device_info_no_id
    mock_duco_api_client.get_device_info.return_value = mock_device_info_no_id
    mock_duco_api_client._api_version = API_V1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT_V1
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "missing_unique_id"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry_v1: ConfigEntry, mock_duco_api_client: MagicMock
) -> None:
    """Test user setup when the device is already configured."""
    # Pre-configure the device
    # mock_config_entry_v1 is added to hass by its fixture

    # Configure API mock for successful validation
    mock_duco_api_client.test_connection.return_value = MOCK_DEVICE_INFO_V1
    mock_duco_api_client.get_device_info.return_value = MOCK_DEVICE_INFO_V1
    mock_duco_api_client._api_version = API_V1

    # Attempt to set up the same device again
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT_V1 # Use V1 host, unique ID matches entry
    )

    # Should abort because unique ID (serial) already exists
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_finish_v2_setup_invalid_key(
    hass: HomeAssistant, mock_duco_api_client: MagicMock
) -> None:
    """Test the finish_v2_setup step with an invalid API key."""
    # Simulate reaching the V2 setup step (context needs host)
    # First validation call (in user step) would have raised ApiAuthError
    # Second validation call (in finish_v2 step) also raises ApiAuthError
    mock_duco_api_client.test_connection.side_effect = ApiAuthError("Invalid Key")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER, CONF_HOST: MOCK_HOST_V2},
        data=MOCK_USER_INPUT_V2, # Provide initial host data
    )
    # Manually advance to the v2 setup step for the test
    result = await hass.config_entries.flow.async_configure(result["flow_id"], MOCK_USER_INPUT_V2) # Simulate user step output
    await hass.async_block_till_done() # Required after configure before next step

    # Check we are in the correct step
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "finish_v2_setup"

    # Provide the invalid key
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "invalid-key"}
    )

    # Should show form again with invalid_auth error
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "finish_v2_setup"
    assert result2["errors"] == {"base": "invalid_auth"}


# === Test Zeroconf Flow ===

MOCK_ZEROCONF_V1_INFO = ZeroconfServiceInfo(
    host=MOCK_HOST_V1,
    port=80,
    hostname="duco-v1-test.local.",
    type="_http._tcp.local.",
    name="duco-v1-test._http._tcp.local.",
    properties={"MAC": MOCK_MAC, "ApiVersion": "1.0.0"}, # Example properties
)

MOCK_ZEROCONF_V2_INFO = ZeroconfServiceInfo(
    host=MOCK_HOST_V2,
    port=443,
    hostname="duco-v2-test.local.",
    type="_https._tcp.local.",
    name="duco-v2-test._https._tcp.local.",
    properties={"MAC": MOCK_MAC, "ApiVersion": "2.0.0", "Serial": MOCK_SERIAL},
)

async def test_zeroconf_flow_success_v1(
    hass: HomeAssistant, mock_duco_api_client: MagicMock
) -> None:
    """Test successful zeroconf flow for a V1 device."""
    mock_duco_api_client.test_connection.return_value = MOCK_DEVICE_INFO_V1
    mock_duco_api_client.get_device_info.return_value = MOCK_DEVICE_INFO_V1
    mock_duco_api_client._api_version = API_V1 # Assume validation passes with V1

    # Initiate zeroconf flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=MOCK_ZEROCONF_V1_INFO
    )
    await hass.async_block_till_done()

    # Should proceed to confirmation step
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert "name" in result["description_placeholders"]

    # Confirm the discovered device
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {} # Empty user input confirms
    )
    await hass.async_block_till_done()

    # Should create the entry
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"DucoBox (?) - {MOCK_SERIAL}"
    assert result2["data"] == MOCK_CONFIG_DATA_V1


async def test_zeroconf_flow_success_v2_needs_key(
    hass: HomeAssistant, mock_duco_api_client: MagicMock
) -> None:
    """Test zeroconf flow for a V2 device that needs an API key."""
    # Zeroconf validation attempts V2 without key, fails with ApiAuthError
    # Confirmation proceeds, then asks for key
    # Final validation with key succeeds
    mock_duco_api_client.test_connection.side_effect = [
        ApiAuthError("Key needed"), # Zeroconf validation fails auth
        MOCK_DEVICE_INFO_V2,       # finish_v2_setup validation succeeds
    ]
    mock_duco_api_client.get_device_info.return_value = MOCK_DEVICE_INFO_V2

    # Initiate zeroconf flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=MOCK_ZEROCONF_V2_INFO
    )
    await hass.async_block_till_done()

    # Should proceed to confirmation (even though validation failed auth)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    # Confirm the discovered device
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    # Should now ask for API key
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "finish_v2_setup"

    # Provide API key
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {CONF_API_KEY: MOCK_API_KEY_V2}
    )
    await hass.async_block_till_done()

    # Should create the entry
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == f"DucoBox (?) - {MOCK_SERIAL}"
    assert result3["data"] == MOCK_CONFIG_DATA_V2


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant, mock_config_entry_v1: ConfigEntry, mock_duco_api_client: MagicMock
) -> None:
    """Test zeroconf flow when the discovered device is already configured."""
    # mock_config_entry_v1 added by fixture

    # Configure API mock for successful validation (needed to get unique ID)
    mock_duco_api_client.test_connection.return_value = MOCK_DEVICE_INFO_V1
    mock_duco_api_client.get_device_info.return_value = MOCK_DEVICE_INFO_V1
    mock_duco_api_client._api_version = API_V1

    # Initiate zeroconf flow for the same device
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=MOCK_ZEROCONF_V1_INFO
    )
    await hass.async_block_till_done()

    # Should abort immediately as unique ID is already configured
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow_connection_error(
    hass: HomeAssistant, mock_duco_api_client: MagicMock
) -> None:
    """Test zeroconf flow where validation fails with connection error."""
    mock_duco_api_client.test_connection.side_effect = ApiConnectionError("Timeout")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=MOCK_ZEROCONF_V1_INFO
    )
    await hass.async_block_till_done()

    # Should abort
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


# === Test Reauth Flow ===

async def test_reauth_flow_success(
    hass: HomeAssistant, mock_config_entry_v2: ConfigEntry, mock_duco_api_client: MagicMock
) -> None:
    """Test successful re-authentication flow."""
    # mock_config_entry_v2 added by fixture

    # Configure API mock for successful validation *during reauth*
    mock_duco_api_client.test_connection.return_value = MOCK_DEVICE_INFO_V2
    mock_duco_api_client.get_device_info.return_value = MOCK_DEVICE_INFO_V2

    # Initiate reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry_v2.entry_id,
        },
        data=mock_config_entry_v2.data, # Pass existing data
    )

    # Should show form for finish_v2_setup (API key step)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "finish_v2_setup" # Skips user step for reauth

    # Provide the (presumably new/correct) API key
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-valid-key"}
    )
    await hass.async_block_till_done()

    # Should finish with reauth_successful abort reason
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    # Verify the config entry data was updated
    assert mock_config_entry_v2.data[CONF_API_KEY] == "new-valid-key"


async def test_reauth_flow_invalid_key(
    hass: HomeAssistant, mock_config_entry_v2: ConfigEntry, mock_duco_api_client: MagicMock
) -> None:
    """Test re-authentication flow with an invalid key provided."""
    # Configure API mock to fail auth during reauth step
    mock_duco_api_client.test_connection.side_effect = ApiAuthError("Invalid Key Again")

    # Initiate reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": mock_config_entry_v2.entry_id},
        data=mock_config_entry_v2.data,
    )

    # Provide invalid key
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "invalid-key-again"}
    )

    # Should show form again with error
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "finish_v2_setup"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_v1_device(
    hass: HomeAssistant, mock_config_entry_v1: ConfigEntry, mock_duco_api_client: MagicMock
) -> None:
    """Test attempting re-authentication on a V1 device."""
    # Initiate reauth flow for V1 entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": mock_config_entry_v1.entry_id},
        data=mock_config_entry_v1.data,
    )

    # Should abort immediately as reauth is not needed for V1
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_not_required_v1"
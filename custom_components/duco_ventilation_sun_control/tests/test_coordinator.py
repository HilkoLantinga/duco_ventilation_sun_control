# === tests/test_coordinator.py ===
"""Test the DucoDataUpdateCoordinator."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from custom_components.duco_ventilation_sun_control.api import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    ApiResponseError,
)
from custom_components.duco_ventilation_sun_control.const import (
    ACTION_SET_OVERRULE,
    DOMAIN,
    DucoCoordinatorData,
    NODE_INFO_KEY_DEVICE_TYPE,
    V1_CANCEL_OVERRULE_VALUE,
    DucoCalibCommand,
    ACTION_SET_CALIBRATION,
    IdentifiedEntity, # Import for type checking
)
from custom_components.duco_ventilation_sun_control.coordinator import (
    DucoDataUpdateCoordinator,
    POST_ACTION_REFRESH_DELAY,
)

# Import fixtures and mock data (using updated realistic data)
from .conftest import (
    MOCK_NORMALIZED_DEVICE_INFO_V1,
    MOCK_RAW_BOXCONFIG_V1,
    MOCK_RAW_ECOCONFIG_V1,
    MOCK_RAW_IPCONFIG_V1,
    MOCK_RAW_NODECONFIG_V1_BOX,
    MOCK_RAW_NODECONFIG_V1_CO2,
    MOCK_RAW_NODECONFIG_V1_RH,
    MOCK_RAW_NODEINFO_V1_BOX,
    MOCK_RAW_NODEINFO_V1_CO2,
    MOCK_RAW_NODEINFO_V1_RH,
    MOCK_RAW_NODELIST_V1,
    setup_integration_v1, # Use fixture that uses realistic data
    setup_integration_v2,
)

# Define realistic node data based on raw mocks for easier use
MOCK_NODE_DATA_V1_BOX = {"info": MOCK_RAW_NODEINFO_V1_BOX, "config": MOCK_RAW_NODECONFIG_V1_BOX}
MOCK_NODE_DATA_V1_CO2 = {"info": MOCK_RAW_NODEINFO_V1_CO2, "config": MOCK_RAW_NODECONFIG_V1_CO2}
MOCK_NODE_DATA_V1_RH = {"info": MOCK_RAW_NODEINFO_V1_RH, "config": MOCK_RAW_NODECONFIG_V1_RH}

# Mock full coordinator data structure using realistic V1 data
MOCK_FULL_COORDINATOR_DATA_V1 = DucoCoordinatorData(
    device_info=MOCK_NORMALIZED_DEVICE_INFO_V1,
    general_config={ # Structure from coordinator's processing
        "box": MOCK_RAW_BOXCONFIG_V1,
        "ip": MOCK_RAW_IPCONFIG_V1,
        "eco": MOCK_RAW_ECOCONFIG_V1,
    },
    nodes={
        "1": MOCK_NODE_DATA_V1_BOX,
        "137": MOCK_NODE_DATA_V1_CO2,
        "138": MOCK_NODE_DATA_V1_RH,
    },
    entities=[] # Populated by _identify_entities
)


async def test_coordinator_successful_update(
    hass: HomeAssistant, mock_duco_api_client: MagicMock, mock_config_entry_v1: ConfigEntry
) -> None:
    """Test a successful data update cycle and entity identification."""
    # Configure API mock responses using realistic V1 data
    mock_duco_api_client.get_device_info.return_value = MOCK_NORMALIZED_DEVICE_INFO_V1
    mock_duco_api_client.get_node_list.return_value = [1, 137, 138]
    async def mock_get_gen_config(area): # Simulate returning raw config per area
        if area == "box": return MOCK_RAW_BOXCONFIG_V1
        if area == "ip": return MOCK_RAW_IPCONFIG_V1
        if area == "eco": return MOCK_RAW_ECOCONFIG_V1
        return {}
    mock_duco_api_client.get_general_config.side_effect = mock_get_gen_config
    async def mock_get_node_info(node_id): # Simulate returning raw info per node
        if node_id == 1: return MOCK_RAW_NODEINFO_V1_BOX
        if node_id == 137: return MOCK_RAW_NODEINFO_V1_CO2
        if node_id == 138: return MOCK_RAW_NODEINFO_V1_RH
        return {}
    mock_duco_api_client.get_node_info.side_effect = mock_get_node_info
    async def mock_get_node_config(node_id): # Simulate returning raw config per node
        if node_id == 1: return MOCK_RAW_NODECONFIG_V1_BOX
        if node_id == 137: return MOCK_RAW_NODECONFIG_V1_CO2
        if node_id == 138: return MOCK_RAW_NODECONFIG_V1_RH
        return {}
    mock_duco_api_client.get_node_config.side_effect = mock_get_node_config

    # Create coordinator instance
    coordinator = DucoDataUpdateCoordinator(hass, mock_config_entry_v1, mock_duco_api_client, 60)

    # Patch device info creation helpers
    with patch("custom_components.duco_ventilation_sun_control.coordinator.async_create_device_info", return_value={"identifiers": {(DOMAIN, "main_dev")}}), \
        patch("custom_components.duco_ventilation_sun_control.coordinator.async_create_node_device_info"):
        await coordinator.async_config_entry_first_refresh()
        await hass.async_block_till_done()

    # --- Assertions ---
    assert coordinator.last_update_success is True
    assert isinstance(coordinator.data, DucoCoordinatorData)
    # Check main data parts
    assert coordinator.data.device_info == MOCK_NORMALIZED_DEVICE_INFO_V1
    assert coordinator.data.general_config["box"] == MOCK_RAW_BOXCONFIG_V1
    assert coordinator.data.nodes["1"] == MOCK_NODE_DATA_V1_BOX
    assert coordinator.data.nodes["137"] == MOCK_NODE_DATA_V1_CO2
    assert coordinator.data.nodes["138"] == MOCK_NODE_DATA_V1_RH
    assert coordinator._box_node_id == 1
    assert coordinator.main_device_info is not None

    # Check entity identification (using new hierarchical keys)
    assert len(coordinator.data.entities) > 0
    identified_keys = {entity.description_key for entity in coordinator.data.entities}

    # Verify some expected keys based on mock data and const definitions
    # Device info sensors
    assert "device.info.power.now" in identified_keys
    assert "device.info.serial" in identified_keys
    # Box config switches/numbers/times/selects
    assert "config.box.time.autodst" in identified_keys
    assert "config.box.fan.maxhighlevel" in identified_keys
    assert "config.box.nightboost.starttime" in identified_keys
    assert "action.calibration_command" in identified_keys # action-based select
    # Node info sensors/selects/numbers (Box Node - ID 1)
    assert "node.info.state" in identified_keys # Operating state select for node 1
    assert "node.info.temperature" in identified_keys # Box node temp sensor
    assert "node.info.countdown" in identified_keys # Box node countdown sensor
    assert "node.info.overrule_percentage" in identified_keys # Box node overrule number
    # Node info/config (CO2 Node - ID 137)
    assert "node.info.co2" in identified_keys # CO2 sensor for node 137
    assert "config.co2.setpoint" in identified_keys # CO2 setpoint number for node 137
    # Node info/config (RH Node - ID 138)
    assert "node.info.humidity" in identified_keys # RH sensor for node 138
    assert "config.rh.delta" in identified_keys # RH delta switch for node 138

    # Check API calls
    mock_duco_api_client.get_device_info.assert_awaited_once()
    mock_duco_api_client.get_node_list.assert_awaited_once()
    assert mock_duco_api_client.get_general_config.call_count == 3
    assert mock_duco_api_client.get_node_info.call_count == 3
    assert mock_duco_api_client.get_node_config.call_count == 3


async def test_coordinator_update_connection_error(
    hass: HomeAssistant, mock_duco_api_client: MagicMock, mock_config_entry_v1: ConfigEntry
) -> None:
    """Test data update failure due to connection error."""
    mock_duco_api_client.get_device_info.side_effect = ApiConnectionError("Timeout")
    coordinator = DucoDataUpdateCoordinator( hass, mock_config_entry_v1, mock_duco_api_client, 60 )
    with pytest.raises(UpdateFailed): await coordinator.async_config_entry_first_refresh()
    assert coordinator.last_update_success is False


async def test_coordinator_update_auth_error(
    hass: HomeAssistant, mock_duco_api_client: MagicMock, mock_config_entry_v2
) -> None:
    """Test data update failure due to authentication error."""
    mock_duco_api_client.get_device_info.side_effect = ApiAuthError("Invalid key")
    coordinator = DucoDataUpdateCoordinator( hass, mock_config_entry_v2, mock_duco_api_client, 60 )
    with pytest.raises(ConfigEntryAuthFailed): await coordinator.async_config_entry_first_refresh()
    assert coordinator.last_update_success is False


async def test_coordinator_update_api_error(
    hass: HomeAssistant, mock_duco_api_client: MagicMock, mock_config_entry_v1: ConfigEntry
) -> None:
    """Test data update failure due to a generic API error."""
    mock_duco_api_client.get_device_info.side_effect = ApiError("Server unavailable")
    coordinator = DucoDataUpdateCoordinator( hass, mock_config_entry_v1, mock_duco_api_client, 60 )
    with pytest.raises(UpdateFailed): await coordinator.async_config_entry_first_refresh()
    assert coordinator.last_update_success is False


async def test_coordinator_partial_failure_node_data(
    hass: HomeAssistant, mock_duco_api_client: MagicMock, mock_config_entry_v1: ConfigEntry
) -> None:
    """Test update cycle completing even if some node data fails."""
    mock_duco_api_client.get_device_info.return_value = MOCK_NORMALIZED_DEVICE_INFO_V1
    mock_duco_api_client.get_node_list.return_value = [1, 137]
    mock_duco_api_client.get_general_config.return_value = {}

    # Node 1 succeeds, Node 137 fails info fetch
    async def mock_fetch_single_node_data(node_id):
        if node_id == 1:
            # Simulate success for node 1
            return {"info": MOCK_RAW_NODEINFO_V1_BOX, "config": MOCK_RAW_NODECONFIG_V1_BOX}
        elif node_id == 137:
            # Simulate failure for node 137
            raise ApiConnectionError("Node 137 timeout")
        return {"info": {}, "config": {}} # Should not be reached

    # Patch the internal helper method used by gather
    with patch.object(DucoDataUpdateCoordinator, '_fetch_single_node_data', side_effect=mock_fetch_single_node_data), \
        patch("custom_components.duco_ventilation_sun_control.coordinator.async_create_device_info"), \
        patch("custom_components.duco_ventilation_sun_control.coordinator.async_create_node_device_info"):

        coordinator = DucoDataUpdateCoordinator( hass, mock_config_entry_v1, mock_duco_api_client, 60 )
        await coordinator.async_config_entry_first_refresh()
        await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    assert coordinator.data is not None
    assert "1" in coordinator.data.nodes
    assert coordinator.data.nodes["1"]["info"] == MOCK_RAW_NODEINFO_V1_BOX # Node 1 data present
    assert "137" in coordinator.data.nodes # Node 137 key exists
    assert coordinator.data.nodes["137"]["info"] == {} # But its data is empty
    assert coordinator.data.nodes["137"]["config"] == {}
    assert len(coordinator.data.entities) > 0 # Entities for node 1 should still be identified


async def test_coordinator_action_calls_api_and_refreshes(
    hass: HomeAssistant, setup_integration_v1
) -> None:
    """Test that coordinator action methods call the API and request refresh."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    mock_api: MagicMock = coordinator.api
    coordinator.async_request_refresh = AsyncMock() # Mock refresh request

    node_id_to_set = 137; overrule_value = 50
    success = await coordinator.async_node_set_overrule(node_id_to_set, overrule_value)

    assert success is True
    mock_api.perform_node_action.assert_awaited_once_with( node_id_to_set, ACTION_SET_OVERRULE, overrule_value )
    coordinator.async_request_refresh.assert_awaited_once()

    mock_api.reset_mock(); coordinator.async_request_refresh.reset_mock()
    calib_command = DucoCalibCommand.START
    success_calib = await coordinator.async_box_set_calibration(calib_command)

    assert success_calib is True
    mock_api.perform_device_action.assert_awaited_once_with( ACTION_SET_CALIBRATION, calib_command.value )
    coordinator.async_request_refresh.assert_awaited_once()


async def test_coordinator_action_api_failure(
    hass: HomeAssistant, setup_integration_v1
) -> None:
    """Test that coordinator actions raise HomeAssistantError on API failure."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    mock_api: MagicMock = coordinator.api
    mock_api.perform_node_action.side_effect = ApiError("Command refused by device")

    with pytest.raises(HomeAssistantError) as excinfo:
        await coordinator.async_node_set_overrule(137, 50)
    assert "Duco command failed" in str(excinfo.value)
    assert "Command refused by device" in str(excinfo.value)
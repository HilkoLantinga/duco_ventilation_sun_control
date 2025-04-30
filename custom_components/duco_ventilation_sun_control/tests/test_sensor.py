# === tests/test_sensor.py ===
"""Test the Duco Ventilation System sensor platform."""

from unittest.mock import MagicMock, patch
from datetime import timedelta # Needed for freezer

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, Platform, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow # Needed for timestamp comparison

# Import constants and types from the integration
from custom_components.duco_ventilation_sun_control.const import (
    DEVICE_INFO_KEY_POWER_NOW, # Original normalized key for mapping
    DEVICE_INFO_KEY_UPTIME,    # Original normalized key for mapping
    DOMAIN,
    NODE_INFO_KEY_CO2,         # Original normalized key for mapping
    NODE_INFO_KEY_DEVICE_TYPE,
    NODE_INFO_KEY_TEMP,
    NODE_INFO_KEY_COUNTDOWN,   # Original normalized key for mapping
    DucoCoordinatorData,
)
from custom_components.duco_ventilation_sun_control.coordinator import (
    DucoDataUpdateCoordinator,
)

# Import fixtures and mock data from conftest
from .conftest import (
    MOCK_NORMALIZED_DEVICE_INFO_V1, # Use normalized data which test setup returns
    MOCK_NODE_DATA_BOX,
    MOCK_NODE_DATA_SENSOR_CO2,
    MOCK_SERIAL,
    setup_integration_v1,
)

# Platform for assertions
PLATFORM = Platform.SENSOR
BOX_NODE_ID = 1
CO2_NODE_ID = 137

# Example Entity IDs using NEW hierarchical keys
POWER_NOW_ENTITY_ID = f"{PLATFORM}.device_info_power_now"
UPTIME_ENTITY_ID = f"{PLATFORM}.device_info_uptime"
NODE_CO2_ENTITY_ID = f"{PLATFORM}.node_info_co2" # Assuming linked to CO2 node device
NODE_TYPE_ENTITY_ID = f"{PLATFORM}.node_info_device_type"
NODE_COUNTDOWN_ENTITY_ID = f"{PLATFORM}.node_info_countdown" # Assuming linked to Box node device


async def test_sensor_entity_creation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_integration_v1: ConfigEntry
) -> None:
    """Test that sensor entities are created correctly with hierarchical keys."""
    # Check device sensors
    entry_power = entity_registry.async_get(POWER_NOW_ENTITY_ID)
    assert entry_power is not None
    assert entry_power.unique_id == f"duco_{setup_integration_v1.entry_id}_device.info.power.now"

    entry_uptime = entity_registry.async_get(UPTIME_ENTITY_ID)
    assert entry_uptime is not None
    assert entry_uptime.unique_id == f"duco_{setup_integration_v1.entry_id}_device.info.uptime"

    # Check node sensors (CO2 node)
    entry_co2 = entity_registry.async_get(NODE_CO2_ENTITY_ID)
    assert entry_co2 is not None
    assert entry_co2.unique_id == f"{MOCK_SERIAL}_node_{CO2_NODE_ID}_node.info.co2"

    entry_type = entity_registry.async_get(NODE_TYPE_ENTITY_ID)
    assert entry_type is not None
    assert entry_type.unique_id == f"{MOCK_SERIAL}_node_{CO2_NODE_ID}_node.info.device_type"

    # Check countdown sensor (Box node)
    entry_countdown = entity_registry.async_get(NODE_COUNTDOWN_ENTITY_ID)
    assert entry_countdown is not None
    # Box node entities linked to main device, use hierarchical key
    assert entry_countdown.unique_id == f"duco_{setup_integration_v1.entry_id}_node.info.countdown"


async def test_sensor_state_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_integration_v1: ConfigEntry
) -> None:
    """Test sensor state updates based on coordinator data with hierarchical keys."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    assert coordinator is not None
    assert coordinator.data is not None

    # --- Test Initial State (based on data from setup_integration_v1 fixture) ---
    # Power Now (Device)
    power_state = hass.states.get(POWER_NOW_ENTITY_ID)
    assert power_state is not None
    assert float(power_state.state) == pytest.approx(MOCK_NORMALIZED_DEVICE_INFO_V1[DEVICE_INFO_KEY_POWER_NOW])

    # CO2 (Node 137)
    co2_state = hass.states.get(NODE_CO2_ENTITY_ID)
    assert co2_state is not None
    # Assume setup fixture mocked get_node_info(137) with MOCK_NODE_DATA_SENSOR_CO2["info"]
    assert int(co2_state.state) == MOCK_NODE_DATA_SENSOR_CO2["info"][NODE_INFO_KEY_CO2]

    # Countdown (Node 1 - Box Node)
    countdown_state = hass.states.get(NODE_COUNTDOWN_ENTITY_ID)
    assert countdown_state is not None
    # Assume setup fixture mocked get_node_info(1) with MOCK_NODE_DATA_BOX["info"]
    assert int(countdown_state.state) == MOCK_NODE_DATA_BOX["info"].get(NODE_INFO_KEY_COUNTDOWN, 0) # Default to 0 if missing


    # --- Test State Update ---
    now = utcnow()
    freezer.move_to(now) # Set current time for uptime calculation

    new_device_info = coordinator.data.device_info.copy()
    new_device_info[DEVICE_INFO_KEY_POWER_NOW] = 30.1
    new_device_info[DEVICE_INFO_KEY_UPTIME] = 7200 # 2 hours

    new_node_137_info = coordinator.data.nodes[str(CO2_NODE_ID)]["info"].copy()
    new_node_137_info[NODE_INFO_KEY_CO2] = 650

    new_node_1_info = coordinator.data.nodes[str(BOX_NODE_ID)]["info"].copy()
    new_node_1_info[NODE_INFO_KEY_COUNTDOWN] = 1190 # Updated countdown

    new_data = DucoCoordinatorData(
        device_info=new_device_info,
        general_config=coordinator.data.general_config,
        nodes={
            str(BOX_NODE_ID): {"info": new_node_1_info, "config": coordinator.data.nodes[str(BOX_NODE_ID)]["config"]},
            str(CO2_NODE_ID): {"info": new_node_137_info, "config": coordinator.data.nodes[str(CO2_NODE_ID)]["config"]},
            # Include other nodes if they were part of the initial setup fixture
        },
        entities=[]
    )

    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    # Check updated states
    power_state_updated = hass.states.get(POWER_NOW_ENTITY_ID)
    assert power_state_updated is not None
    assert float(power_state_updated.state) == pytest.approx(30.1)

    co2_state_updated = hass.states.get(NODE_CO2_ENTITY_ID)
    assert co2_state_updated is not None
    assert int(co2_state_updated.state) == 650

    countdown_state_updated = hass.states.get(NODE_COUNTDOWN_ENTITY_ID)
    assert countdown_state_updated is not None
    assert int(countdown_state_updated.state) == 1190

    # Test timestamp sensor formatting (Uptime)
    uptime_state = hass.states.get(UPTIME_ENTITY_ID)
    assert uptime_state is not None
    expected_uptime_dt = now - timedelta(seconds=7200)
    expected_uptime_str = expected_uptime_dt.isoformat(timespec="seconds")
    assert uptime_state.state == expected_uptime_str


async def test_sensor_unavailability(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_integration_v1: ConfigEntry
) -> None:
    """Test sensor becomes unavailable when coordinator fails."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    mock_api: MagicMock = coordinator.api

    power_state = hass.states.get(POWER_NOW_ENTITY_ID)
    assert power_state is not None and power_state.state != STATE_UNAVAILABLE

    mock_api.get_device_info.side_effect = ApiConnectionError("Device offline")
    freezer.tick(timedelta(seconds=70))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    power_state_unavailable = hass.states.get(POWER_NOW_ENTITY_ID)
    assert power_state_unavailable is not None and power_state_unavailable.state == STATE_UNAVAILABLE

    # Simulate recovery
    mock_api.get_device_info.side_effect = None
    mock_api.get_device_info.return_value = MOCK_NORMALIZED_DEVICE_INFO_V1
    mock_api.get_node_list.return_value = [BOX_NODE_ID, CO2_NODE_ID] # Restore nodes
    mock_api.get_node_info.side_effect = lambda nid: MOCK_NODE_DATA_BOX["info"] if nid==BOX_NODE_ID else MOCK_NODE_DATA_SENSOR_CO2["info"]
    mock_api.get_node_config.side_effect = lambda nid: MOCK_NODE_DATA_BOX["config"] if nid==BOX_NODE_ID else MOCK_NODE_DATA_SENSOR_CO2["config"]
    mock_api.get_general_config.return_value = {}

    freezer.tick(timedelta(seconds=70))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    power_state_available_again = hass.states.get(POWER_NOW_ENTITY_ID)
    assert power_state_available_again is not None and power_state_available_again.state != STATE_UNAVAILABLE
    assert float(power_state_available_again.state) == pytest.approx(MOCK_NORMALIZED_DEVICE_INFO_V1[DEVICE_INFO_KEY_POWER_NOW])
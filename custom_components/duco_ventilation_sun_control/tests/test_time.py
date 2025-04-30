# === tests/test_time.py ===
"""Test the Duco Ventilation System time platform."""

from datetime import time
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_VALUE, STATE_UNAVAILABLE, Platform, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

# Import constants and types
from custom_components.duco_ventilation_sun_control.const import (
    DOMAIN,
    KEY_MODULE_NIGHTBOOST, # Module name
    KEY_PARAM_NB_STARTTIME, # API Param name
    KEY_PARAM_NB_STOPTIME,
    NODE_CONFIG_KEY_VALUE, # Key where value is stored in dict
    DucoCoordinatorData,
)
from custom_components.duco_ventilation_sun_control.coordinator import (
    DucoDataUpdateCoordinator,
)

# Import fixtures and mock data
from .conftest import (
    MOCK_SERIAL,
    setup_integration_v1,
)

# Platform for assertions
PLATFORM = Platform.TIME

# Example Entity IDs using NEW hierarchical keys
NB_START_ENTITY_ID = f"{PLATFORM}.config_box_nightboost_starttime"
NB_STOP_ENTITY_ID = f"{PLATFORM}.config_box_nightboost_stoptime"


async def test_time_entity_creation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_integration_v1: ConfigEntry
) -> None:
    """Test that time entities are created correctly with hierarchical keys."""
    # Check NightBoost Start Time
    entry_start = entity_registry.async_get(NB_START_ENTITY_ID)
    assert entry_start is not None
    assert entry_start.unique_id == f"duco_{setup_integration_v1.entry_id}_config.box.nightboost.starttime"

    # Check NightBoost Stop Time
    entry_stop = entity_registry.async_get(NB_STOP_ENTITY_ID)
    assert entry_stop is not None
    assert entry_stop.unique_id == f"duco_{setup_integration_v1.entry_id}_config.box.nightboost.stoptime"


@pytest.mark.parametrize(
    "entity_id, data_path, value_key, initial_api_value_minutes, expected_initial_state_str",
    [
        # Test Start Time using new key structure
        (NB_START_ENTITY_ID, ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STARTTIME], NODE_CONFIG_KEY_VALUE, 1320, "22:00:00"),
        (NB_START_ENTITY_ID, ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STARTTIME], NODE_CONFIG_KEY_VALUE, 0, "00:00:00"),
        (NB_START_ENTITY_ID, ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STARTTIME], NODE_CONFIG_KEY_VALUE, None, None),
        # Test Stop Time using new key structure
        (NB_STOP_ENTITY_ID, ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STOPTIME], NODE_CONFIG_KEY_VALUE, 360, "06:00:00"),
        (NB_STOP_ENTITY_ID, ['box', KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STOPTIME], NODE_CONFIG_KEY_VALUE, 1439, "23:59:00"),
    ]
)
async def test_time_state_update(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry,
    entity_id: str, data_path: list[str], value_key: str | None,
    initial_api_value_minutes: int | None, expected_initial_state_str: str | None
) -> None:
    """Test time entity state updates based on coordinator data with hierarchical keys."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]

    # --- Setup Initial State ---
    current_data = coordinator.data or DucoCoordinatorData()
    new_general_config = current_data.general_config.copy() # Operate on general_config

    # Place initial value in the correct location (nested under value_key)
    current_level = new_general_config
    for i, key in enumerate(data_path):
        if i == len(data_path) - 1: # Last key is the parameter name
            param_key = key
            if value_key: # Value is nested under value_key
                if param_key not in current_level or not isinstance(current_level.get(param_key), dict): current_level[param_key] = {}
                if initial_api_value_minutes is None: current_level[param_key].pop(value_key, None); \
                    if not current_level[param_key]: current_level.pop(param_key, None)
                else: current_level[param_key][value_key] = initial_api_value_minutes
            else: # Should not happen for time entities based on map
                pytest.fail("Time entity map missing value_key")
        else: # Navigate/create intermediate dicts
            if key not in current_level: current_level[key] = {}
            current_level = current_level[key]

    new_data = DucoCoordinatorData(
        device_info=current_data.device_info,
        general_config=new_general_config,
        nodes=current_data.nodes,
        entities=[] )

    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    # Check state
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found after state update."
    expected_state = expected_initial_state_str if expected_initial_state_str is not None else STATE_UNKNOWN # Use STATE_UNKNOWN for time
    assert state.state == expected_state


async def test_time_set_value_success(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test successfully setting a time value via service call with hierarchical keys."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]

    # --- Test setting Start Time ---
    time_to_set = time(21, 30, 0); expected_api_minutes = 1290
    with patch.object(coordinator, "async_box_set_config") as mock_set_box_config:
        await hass.services.async_call( TIME_DOMAIN, SERVICE_SET_VALUE, {ATTR_ENTITY_ID: NB_START_ENTITY_ID, ATTR_VALUE: time_to_set.isoformat()}, blocking=True)
        await hass.async_block_till_done()
        # Verify coordinator method call uses original API param name
        mock_set_box_config.assert_awaited_once_with(KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STARTTIME, expected_api_minutes)

    # --- Test setting Stop Time ---
    mock_set_box_config.reset_mock()
    time_to_set_stop = time(7, 0, 0); expected_api_minutes_stop = 420
    with patch.object(coordinator, "async_box_set_config") as mock_set_box_config:
        await hass.services.async_call( TIME_DOMAIN, SERVICE_SET_VALUE, {ATTR_ENTITY_ID: NB_STOP_ENTITY_ID, ATTR_VALUE: time_to_set_stop.isoformat()}, blocking=True)
        await hass.async_block_till_done()
        # Verify coordinator method call uses original API param name
        mock_set_box_config.assert_awaited_once_with(KEY_MODULE_NIGHTBOOST, KEY_PARAM_NB_STOPTIME, expected_api_minutes_stop)


async def test_time_set_value_api_error(
    hass: HomeAssistant, setup_integration_v1: ConfigEntry
) -> None:
    """Test error handling when API call fails during set_value."""
    coordinator: DucoDataUpdateCoordinator = hass.data[DOMAIN][setup_integration_v1.entry_id]
    with patch.object(coordinator, "async_box_set_config", side_effect=HomeAssistantError("Simulated API fail")):
        with pytest.raises(HomeAssistantError) as excinfo:
            await hass.services.async_call( TIME_DOMAIN, SERVICE_SET_VALUE, {ATTR_ENTITY_ID: NB_START_ENTITY_ID, ATTR_VALUE: "20:00:00"}, blocking=True)
        assert "Simulated API fail" in str(excinfo.value)